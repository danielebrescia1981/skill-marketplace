# Audit mode — check an existing repo against house conventions

**Load:** only in Audit mode. Don't load the other modules up front. Open one only to explain a finding that needs its detail.

## Procedure

1. **Establish shape** from `CLAUDE.md § Shape` if present. Otherwise infer: `django_rls` in deps → tenant; `damsso` or `socialaccount` → SSO; `pytest-gxp` / `validation/` → GxP; `stripe` → billing; `ninja`/`rest_framework`/`mcpz` → API.
2. **Run the probes below** (read-only). Delegate to an Explore agent if the repo is large; ask it for evidence (file:line), not opinions.
3. **Report** as a table: `Area | Finding | Evidence | Severity (🔴 fix now / 🟡 fix soon / 🟢 nice) | Fix (one line)`. Order by severity. Flag doc drift (CLAUDE.md/README facts contradicted by code) as its own row; it misleads every future session.
4. Offer to fix the 🔴 rows. Don't fix anything unasked.

## Probes

**Always**

| Check | Probe | Known offender |
|---|---|---|
| CI test gate before deploy | `.github/workflows/*` contain a pytest job that deploy `needs` | appsfolio, eqms, gxpsign, meetingsignals |
| `DEBUG` parsed as bool | `grep -n "DEBUG *=" src/config/settings.py` → `env.bool` | appsfolio `config.get("DEBUG", False)` |
| `STORAGES` not `STATICFILES_STORAGE` | grep both | meetingsignals |
| Secrets fail closed | no real-looking defaults for `SECRET_KEY`, `SENTRY_DSN`, webhook secrets | gxpsign DSN default |
| Health path consistent | route vs Dockerfile `HEALTHCHECK` vs compose vs workflow | gxpsign `/health/` vs `/ht/` |
| Pre-commit ruff args | `--select=I, E, F…` split into separate args | gxpsign |
| Declared deps used / used deps declared | `--cov` without pytest-cov; factory-boy unused | appsfolio |
| JS pinned | `@3.x.x`, unpinned CDN, no SRI | meetingsignals, gxpsign |
| Docs tool single | zensical vs mkdocs in justfile vs Dockerfile | meetingsignals |
| Backups exist and restore tested | host cron / script / runbook | meetingsignals none |
| `/metrics` not public | route auth / network binding | meetingsignals |
| Stale recipes | `just --list` recipes pointing at missing dirs | appsfolio `deploy-*` |
| Debug leftovers | `test_zz*`, `print(` in tests, stray files at root | eqms |
| CLAUDE.md facts | Python/Django version, user model path, server (gunicorn/uvicorn), orchestration | appsfolio, gxpsign, meetingsignals |
| Prod pinned | no `:latest` in prod compose/workflow; version tag created post-verify | — |
| Logout on GET | `ACCOUNT_LOGOUT_ON_GET` | meetingsignals |

**Tenant (if on)**

| Check | Probe |
|---|---|
| App role can't bypass | `SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user` on the `default` alias → both false |
| Every tenant table has a policy | the meta-test exists and passes; `manage.py audit_rls` (django-rls 2.x) |
| Historical tables covered | `Historical*` in `_MODELS` of rls_enable migrations |
| django-rls receivers | disabled via `DJANGO_RLS` settings (2.x) or disconnected (0.4.x) |
| `post_migrate` auto-enable silently no-op | apps under a package prefix (`apps.folio`) never match, so policies must come from migrations |
| Context from user, not host | middleware sets `rls.tenant_id` from `request.user.tenant` |
| `.using("admin")` justified | each use has a why-comment |
| Legacy tenancy code removed | unused thread-local managers (appsfolio `apps/folio/tenant.py`) |

**SSO (if on)**: policy hook configured (not default JIT); enforcement raises in `pre_authenticate`; domain matching fails closed on ambiguity; `FERNET_KEYS` set.

**Stripe (if on)**: webhook signature verified with a required secret; idempotency table; retryable vs ack split.

**GxP (if on)**: append-only audit models raise on update/delete; fresh re-auth per signature (no session window); pytest-gxp pinned exactly; gap report test; prod promotes by digest; CHANGELOG has Validation Impact.
