# DevOps — Docker, CI, deploy, observability

**Load:** when the app first needs to run somewhere other than a laptop. **Assets:** `assets/skeleton/Dockerfile`, `assets/skeleton/dot-dockerignore`, `assets/skeleton/docker-compose.yml`, `assets/skeleton/dot-github/workflows/{ci,deploy-test,deploy-prod}.yml`.

## Target (house default)

- One self-hosted Docker host, Traefik in front (Let's Encrypt, behind Cloudflare Full-Strict), Postgres 18 on the host network or a managed DB.
- Compose stacks live in the separate **`devmo_apps`** repo at `/home/devmo/apps/apps/<app>-{test,prod}/` with a `.env` each, updated by `just update-<app>-{test,prod}` on the server. Container names are `<app>-<env>-app` and `<app>-<env>-worker`, and the workflows depend on those names.
- Images live on **GHCR**. Ports on the shared host are allocated per app, and admin ports bind only to the Tailscale IP.
- If the compose file lives in the app repo instead (refractions `website/deploy/server/*.compose.yml`), scp it on every deploy so the repo copy stays authoritative.

Other targets (Fly, Render, ECS) keep everything below except the SSH steps.

## Dockerfile (multi-stage, `Dockerfile`)

1. **builder**: `python:3.14-slim`, `COPY --from=ghcr.io/astral-sh/uv:<pinned> /uv /uvx /bin/`, `UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy`. `uv sync --frozen --no-dev --no-install-project` first (cached layer), then copy `src/` and sync again.
2. **css**: download the pinned Tailwind Linux binary and build `output.css --minify`.
3. **docs** (if /help/): `uvx zensical build`.
4. **runtime**: slim, only runtime libs (`libpq5`, `curl` for the healthcheck, plus WeasyPrint/LibreOffice if needed, each commented with why). Copy `.venv`, source, built CSS and docs. `ARG APP_VERSION` → `ENV APP_VERSION`. `collectstatic` **at build time with dummy secrets scoped to that RUN line only**. Non-root `appuser`. `HEALTHCHECK CMD curl -fsS http://127.0.0.1:8000/ht/`. `CMD gunicorn --chdir /app/src --workers ${WEB_CONCURRENCY:-2} config.wsgi` (uvicorn `config.asgi` only with Channels).
- The worker is the same image: `command: python manage.py procrastinate worker`.
- `.dockerignore` excludes `.env*` (keep `.env.example`), keys, `.git`, `tests/`, `docs/`, `node_modules`, `staticfiles`, `help_site`.

## Local compose (`docker-compose.yml`)

`db` (postgres:18, unique host port, `pg_isready` healthcheck, `[tenant]` role-init script mounted — *only that file*, not all of `scripts/`) + `mailpit`. `web` and `worker` sit behind `profiles: ["app"]`, so `just db` stays DB-only but `docker compose --profile app up` smoke-tests the real image.

## CI — a gate first (`ci.yml`)

Runs on push and PR for all branches: Postgres service → `uv sync --frozen` → `just check` (ruff, `manage.py check`, `makemigrations --check`) → `just test`. **Four of the five repos deploy with no test gate. Don't copy that.** `deploy-test` runs `needs: ci` (call it as a reusable workflow, or just rely on branch protection requiring CI on `test`).

Pin third-party actions by SHA with a version comment (`uses: appleboy/ssh-action@<sha> # v1.0.3`). Refractions does this; the others don't.

## Deploy to test (`deploy-test.yml`) — automatic on push to `test`

build → push `:test` and `:test-<full sha>` (with `build-args: APP_VERSION=test-<sha>`, `cache-from/to: type=gha`) → SSH: `docker login` with `GHCR_PAT`, `just update-<app>-test`, `docker exec <app>-test-app python manage.py migrate [--database=admin]`, `check --deploy`, then idempotent seed commands → **verify**: curl `/ht/` and fail the job (dumping `docker logs --tail 100`) if it isn't 200 → step summary.

Refractions' deploy-prod comment is the reason for the verify step: collectstatic failed about 59 times and "every one of those was reported as a successful deploy".

## Deploy to prod (`deploy-prod.yml`) — manual, promote by digest

`gh workflow run deploy-prod.yml --ref main -f version=vX.Y.Z`. Two jobs (gxpsign):

- **qualify** (changes nothing): validate the `vX.Y.Z` format; refuse if that tag already exists in the registry (versions are immutable); resolve the digest of `:test-$GITHUB_SHA` and fail if there isn't one ("push this commit to test first"); SSH to confirm the *test containers are running that digest*; write an evidence table to the job summary.
- **deploy**: `docker buildx imagetools create -t :vX.Y.Z <image>@<digest>` (a retag, never a rebuild); pin `APP_VERSION=vX.Y.Z` in the prod `.env`; `just update-<app>-prod`; verify both containers run that tag *and* digest and that `printenv APP_VERSION` matches; migrate; `/ht/` check; **then** create and push the git tag, so a tag never names a release that didn't reach prod.

No `:latest` anywhere. Prod always runs a pinned, qualified version. Non-GxP apps can drop the SSH digest confirmation but keep the retag-not-rebuild.

Required repo settings: variables `SERVER_HOST`, `SERVER_USER`; secrets `SERVER_SSH_KEY`, `GHCR_PAT`. The `production` environment records deploy history.

## Migrations

Deploy then migrate: the new container runs, then `migrate` executes in it. That's safe because migrations are additive. For destructive changes use expand → deploy → contract across two releases. With tenancy, always `--database=admin`, then `check --deploy` (asserts the app role can't bypass RLS).

## Health, logs, errors, metrics

- `/ht/`: DB `SELECT 1`, 503 on failure, used by Docker `HEALTHCHECK`, Traefik and the deploy verify step. Keep it out of `SECURE_SSL_REDIRECT` (`SECURE_REDIRECT_EXEMPT = [r"^ht/$"]`), Sentry traces and access logs (a logging filter on the path). One path only; gxpsign's compose probing `/health/` against a `/ht/` route is the drift to avoid.
- **Logging**: loguru bridged from stdlib (`LOGGING_CONFIG = None` + `InterceptHandler`) to stdout in containers. `log_security_event(...)` / `log_gxp_event(...)` helpers use `logger.bind(event_type=…)`. A request-ID middleware (`X-Request-ID`, `logger.contextualize`). No log files inside containers unless shipped.
- **Sentry**: test + prod only, `send_default_pii=False`, a `before_send` dropping known noise (client disconnects, worker reconnects), `release=myapp@{APP_VERSION}`, and a user-feedback widget on the 500 page.
- **Metrics** (optional): `django-prometheus` at `/metrics`, **staff-only or bound to the internal network**. Meetingsignals exposes it publicly. Postgres exporter on the host.
- **Uptime**: an external monitor (Uptime Kuma) on `/ht/` or `/ping/`.

## Backups (before launch, not after)

A cron on the host: `pg_dump --format=custom | gzip` per prod DB to off-box storage (R2/S3). Fail loudly if the dump is under 1 KB, keep 14–30 days, and **test a restore** into a scratch DB quarterly (in LAUNCH.md). Meetingsignals still has "- [ ] Backup strategy". Don't ship like that.

## Dev copy of prod data

`just db-copy-prod` (appsfolio): SSH tunnel → `pg_dump --format=custom` → `DROP DATABASE … WITH (FORCE)` → `pg_restore --no-owner --no-privileges` → migrate. The password comes from `: "${PROD_DB_PASSWORD:?set it}"`, never a file in the repo. Consider whether the data may leave prod at all: for GxP or customer PII, usually not.

## Releases and versioning

Semver tags `vX.Y.Z` created by the prod workflow. The in-app footer shows `APP_VERSION`. For desktop or distributed artefacts, the build number is `git rev-list --count HEAD` (needs `fetch-depth: 0`), with one tag suffix per channel (`-beta.N`) so a mistyped tag does nothing rather than shipping to the wrong channel (refractions).
