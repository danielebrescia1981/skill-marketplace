# Testing

**Load:** when writing the first tests, or when adding e2e. **Assets:** `assets/skeleton/tests/conftest.py`, `test_smoke.py`, `test_rls.py`.

## Layout and config

- pytest-django. `[tool.pytest.ini_options]` in pyproject (or `pytest.ini`):
  ```toml
  DJANGO_SETTINGS_MODULE = "config.settings_test"
  pythonpath = ["src"]
  addopts = "--strict-markers --ignore=tests/e2e"
  markers = ["unit", "integration", "e2e", "security", "slow", "gxp"]
  ```
- Tests live flat in `tests/test_<module>.py`, with `tests/e2e/` separate and `tests/fixtures/` for files.
- Run via `just test` so env and settings are always right. `just test -k name -x` passes args through.
- **Postgres in tests.** Mandatory with RLS or Procrastinate. The compose DB pre-creates `test_myapp`, and `TEST_DB_NAME` is overridable so parallel runs don't collide.

## Fixtures and factories

- factory-boy factories, `tenant_factory` / `user_factory` style fixtures. Two of the repos installed factory-boy and never used it, building objects by hand in every test. Use it.
- Role-based client fixtures: `client_for(user)`, `org_admin_client`, `reader_client`, `paid_client`.
- An autouse fixture ensures `Site(id=1)` exists (allauth).
- A session fixture swaps `staticfiles` to plain `StaticFilesStorage` so templates render without `collectstatic`.
- A loguru → `caplog` bridge if loguru is used.

## What every app tests

| Area | Tests |
|---|---|
| URLs & rendering | every named URL resolves; every public page renders 200 anonymous; every app page redirects anonymous → login |
| Permissions | each role × each mutating view (Reader can't POST anywhere) |
| Tenancy | see tenancy-rls.md § Tests, including the meta-test |
| Security posture | `check --deploy` is clean under prod-like settings; the headers you promise are present; `/.well-known/change-password` redirects |
| Webhooks | signature failure → 400, duplicate → 200 no-op, retryable → 500 |
| Forms | create forms on `db_default` PK models don't treat new instances as existing (foundation.md § PK trap) |
| Static | every `{% static %}` a template references exists (tests use plain storage; prod manifest storage 500s on a missing file) |
| Help | every `help_url` anchor exists in the built site |
| Drift | generated files match their generators (`--check`), MCP surface snapshot, migrations (`makemigrations --check`) |

**Meta-tests over instance tests.** When a mistake could happen again in a new app or model, assert over *all* of them (every tenant table, every URL, every anchor) so the next one is caught automatically.

## E2E (Playwright)

- `pytest-playwright` against `live_server`, with `settings_e2e.py` doing `from .settings import *` so middleware, CSP and RLS behave as in prod. Only mail (Mailpit), media dir and inline tasks change.
- `django_db(transaction=True)`. Per-run unique slug/email prefixes, swept at the end.
- Page objects in `tests/e2e/pages.py`. A Mailpit HTTP client reads verification and invite emails.
- `just e2e`, and `just e2e-file FILE` for headed mode. Traces go to `artifacts/traces/` (gitignored).
- Smoke tests take `SMOKE_TEST_URL` so the same suite runs against test and prod after deploy (appsfolio `just smoke-test` / `smoke-prod`).

## Coverage

`pytest-cov` in dev deps if you use `--cov`: appsfolio's `just test-cov` fails because it isn't installed. Coverage is informational. For GxP, requirement traceability (pytest-gxp) is the coverage that counts.

## CI

The CI workflow (devops.md) runs `just check` + `just test` against a Postgres service container on every push and PR, and deploy jobs `need:` it. Tests exit code 5 (no tests collected) is a failure, not a pass. Don't copy refractions' deploy-test, which treats it as a pass.
