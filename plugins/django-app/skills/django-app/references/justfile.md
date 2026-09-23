# Justfile conventions

**Load:** always in Create mode; in Extend mode when adding recipes. **Asset:** `assets/skeleton/justfile`.

`just` is the only entry point a human or agent needs. If a task is done twice, it becomes a recipe. CLAUDE.md says "Run tests with `just test`, not bare `pytest`" so env and settings are always right.

## Rules

- `default: @just --list`. A comment line above each recipe is its `--list` description. Group with `# ----- Section -----` banners.
- `set shell := ["bash", "-uc"]`. Use the `#!/usr/bin/env bash` + `set -euo pipefail` shebang form for multi-line logic.
- Names in one vocabulary across repos: `setup install dev stop db db-stop db-reset db-shell migrate makemigrations superuser shell worker css test lint format typecheck check e2e help-build clean`. An agent that knows one repo knows them all.
- Recipe dependencies express order: `setup: install db migrate`, `dev: db css`.
- Private helpers start with `_` (`_ensure-services`), hidden from `--list`.
- Variables at the top (`APP`, `DEV_PORT`, `TAILWIND_VERSION`, `SERVER`). Override on the CLI: `just PROD_URL=… build`.
- `*ARGS` passes through flags: `test *ARGS: uv run pytest {{ARGS}}`.
- Idempotent everything: `tailwind-setup` checks its version before downloading; `superuser` creates or resets; `db` waits (`--wait`) on healthchecks.
- Destructive recipes confirm (`read -p … [y/N]`), prod variants always.
- Stop commands tolerate absence: `-@pkill -f "…" 2>/dev/null || true`.
- **Fail loudly in build steps** — e.g. refractions `manifest-prod` greps for a leftover `localhost` and exits 1; a release recipe refuses a shallow clone.

## `just dev` — one terminal, everything running

The pattern all five repos converged on:

```bash
trap 'just stop; exit 0' INT TERM
(portless myapp bash -c 'uv run python manage.py runserver $HOST:$PORT' 2>&1 | sed 's/^/[django]   /') &
(bin/tailwindcss … --watch 2>&1 | sed 's/^/[css]      /') &
(uv run python manage.py procrastinate worker 2>&1 | sed 's/^/[worker]   /') &
wait
```

- Each process's output is prefixed and padded so interleaved logs stay readable.
- **portless** gives real HTTPS at `https://myapp.localhost/` (and `https://<tenant>.myapp.localhost/` with `--wildcard`) — no `/etc/hosts`, secure cookies and WebAuthn work locally. Probe the proxy with `curl` before `sudo portless proxy start` so the password is asked once per boot, not every run.
- Add `stripe listen --forward-to …/webhook/` when billing is on, a docs watcher when help is on.
- Print the URLs (app, tenant, Mailpit, Postgres port) before `wait`.

## Nested justfiles

When a sub-tool has its own lifecycle (a Stripe product-sync tool, a validation suite, a website in a monorepo), give it a justfile in its directory and delegate: `stripe *ARGS: cd stripe && just {{ARGS}}`. gxpsign's `validation/justfile` header says "This file IS the procedure" — when a recipe *is* a controlled procedure, its checklist doc is a reading copy of it, not the other way round.

## Remote ops

Ops against deployed environments go through just, never ad-hoc ssh:

```just
remote ENV *ARGS:
    ssh -t {{SERVER}} "docker exec -it {{APP}}-{{ENV}}-app python manage.py {{ARGS}}"
```

Management commands used this way print the payload to stdout and the summary to stderr, so `KEY=$(just remote prod dev_license)` scripts cleanly (refractions).

Secrets for local signing/release recipes auto-load and no-op when absent: `set -a; [ -f .env.signing ] && . .env.signing; set +a`.

## macOS native libs

If WeasyPrint/cairo are needed (PDFs), export the Homebrew lib path once at the top, not per recipe:

```just
export DYLD_LIBRARY_PATH := "/opt/homebrew/lib:" + env_var_or_default("DYLD_LIBRARY_PATH", "")
```
