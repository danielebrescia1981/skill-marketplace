---
name: django-app
description: "Create, extend, or audit a Django web app (SaaS, internal tool, regulated/GxP system) using house conventions: uv + src/ layout, Django 6 + Python 3.14, env-driven settings, justfile, portless local HTTPS, Postgres-only infra (Procrastinate queue, DatabaseCache, no Redis), Tailwind v4 standalone + HTMX + Alpine, allauth email login, GHCR images deployed over SSH, dev→test→main promotion. Starts with qualifying questions — is it tenant-based (→ django-rls row-level security), does it need SSO, is it GxP/21 CFR Part 11, does it bill with Stripe, does it expose an API/MCP — and loads only the reference modules those answers need. Use when the user says 'new Django app', 'scaffold a Django project', 'start a SaaS in Django', 'add multi-tenancy/RLS', 'add SSO', 'set up deploy for this Django app', 'make this repo match our conventions', or asks to audit a Django repo against best practices. Do NOT use for Flask/FastAPI projects or for non-Django frontends."
license: Proprietary
metadata:
  version: 1.0.0
  derived_from: [appsfolio, eqms, gxpsign, meetingsignals, refractions]
  composes_with: [gxp-doc, design-md, uv]
---

# Django App

House conventions for Django apps, distilled from five production repos. **This file is a router.** Ask the qualifying questions, then load only the modules that apply — every module in `references/` is self-contained and marked with when it is needed.

## Step 0 — Mode

| User wants | Mode |
|---|---|
| A new app | **Create** — Steps 1–4 in order |
| Add a capability to an existing app (tenancy, SSO, billing, deploy…) | **Extend** — Step 1 for that capability only, then its module |
| "Does this repo follow our conventions?" | **Audit** — load `references/audit.md` only |

## Step 1 — Qualifying questions

Ask with `AskUserQuestion` (max 4 per call → two calls). Skip any the user already answered. Defaults in **bold**.

**Round 1 — shape**
1. **Tenant-based?** Do multiple customer organisations share one deployment with isolated data? → *yes* loads `tenancy-rls.md` (django-rls, two DB roles). Per-user data only → **no**.
2. **SSO?** **none** (email + password) / *per-tenant enterprise SSO* (OIDC/SAML configured by each customer org → damsso; requires tenancy) / *social login* (Google/Microsoft buttons → allauth socialaccount). Anything but none loads `sso.md`.
3. **Regulated (GxP / 21 CFR Part 11 / Annex 11)?** → *yes* loads `gxp.md`. **no**.
4. **Paid subscriptions (Stripe)?** → *yes* loads `billing-stripe.md`. **no**.

**Round 2 — surface**
5. **Public API or MCP server** for customers/agents? → loads `api-mcp.md`. **no**.
6. **Realtime** (live-updating pages over WebSockets)? → adds Channels + Redis, the one sanctioned exception to "no Redis" (see `foundation.md` § Realtime). **no**.
7. **Marketing site + user help docs served by the same container** at `/` and `/help/`? → **yes** (the `/help/` section in `frontend.md`).
8. **Deploy target**: **self-hosted Docker Compose server via the `devmo_apps` repo** (house default) / other. Other → keep `devops.md` principles, swap the SSH steps.

Then ask in plain text (not a picker): **product name**, **slug** (lowercase, used for containers/images/DB roles), **production domain**, and pick **free local ports** — check `lsof -iTCP -sTCP:LISTEN` and existing repos' compose files; each app gets its own Postgres port (used so far: 5434 refractions, 5435 gxpsign, 5436 eqms, 5452 meetingsignals) and dev-server port.

Record the answers at the top of the new repo's `CLAUDE.md` under `## Shape` so future sessions (and this skill in Extend mode) know which modules apply without re-asking.

## Step 2 — Module map

Load a module only when its trigger holds. Never load a module "for context".

| Module | Load when | Stage |
|---|---|---|
| `references/foundation.md` | always (Create) | scaffold |
| `references/justfile.md` | always (Create) | scaffold |
| `references/repo-management.md` | always (Create) | scaffold |
| `references/frontend.md` | app has server-rendered UI (almost always) | scaffold |
| `references/tasks-email.md` | always unless the app sends no email and has no background work | scaffold |
| `references/tenancy-rls.md` | Q1 = yes | features — **before the first domain model** |
| `references/sso.md` | Q2 ≠ none | features |
| `references/billing-stripe.md` | Q4 = yes | features |
| `references/api-mcp.md` | Q5 = yes | features |
| `references/gxp.md` | Q3 = yes | features, and again at release |
| `references/testing.md` | when writing the first tests | quality |
| `references/devops.md` | when the app first needs to run somewhere other than a laptop | deploy |
| `references/security.md` | before first external user; pre-launch | launch |
| `references/audit.md` | Audit mode only | — |

`assets/skeleton/` is a complete, tested project (tenant and non-tenant variants both pass `just check` + `just test`). Render it; never hand-copy:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/django-app/scripts/render.py \
  ${CLAUDE_PLUGIN_ROOT}/skills/django-app/assets/skeleton ~/code/<slug> \
  --on tenant,help \
  --set myapp=<slug> MyApp="<Product Name>" myapp.com=<prod domain> \
        __DB_PORT__=<port> __DEV_PORT__=<port> __SERVER__=<ssh host alias>
```

Features: `tenant`, `help` (skeleton code), plus `stripe`, `gxp` (justfile/workflow hooks only; the module supplies the code). Blocks are `# [x] … # [/x]` (keep if on) and `# [!x] … # [/!x]` (keep if off). Files wholly inside a disabled block aren't written, and `dot-*` paths become dotfiles. The script refuses a non-empty destination (`--force` to override) and exits 2 if a `__PLACEHOLDER__` is left unfilled. SSO, billing, API and GxP code is added afterwards from each module, not rendered.

## Step 3 — Build order (Create mode)

1. **Scaffold**: render the skeleton, then in the new repo run `git init -b dev`, `cp .env.example .env`, `uv lock`, `just setup`, `uv run python manage.py makemigrations <apps>` (tenant: `tenants accounts`), `just migrate`. Skim foundation → justfile → repo-management → frontend → tasks-email only for what you change beyond the skeleton. Exit check: `just check && just test` pass; `just dev` serves `https://<slug>.localhost/` and `/ht/` returns 200.
2. **Tenancy** (if on) — tenant + user models, roles, router, middleware, RLS migration and the policy meta-test *before any domain model exists*. Retrofitting RLS onto a live schema is the incident appsfolio's `PLAN_RLS_SECURITY.md` records.
3. **Auth / SSO / billing / API / GxP** modules as selected.
4. **Domain features.**
5. **Deploy** — devops. Exit check: push to `test` deploys and `/ht/` answers on the test URL.
6. **Launch** — security checklist, backups, `LAUNCH.md` empty of 🔴 items.

Commit at each exit check. Don't commit to `main`; work on `dev` (see repo-management).

## Non-negotiables (apply regardless of modules)

These are the decisions all five repos converged on, or were burned by skipping. Details live in the modules; this is the list to hold in mind.

- **Postgres for everything** — queue (Procrastinate), cache (`DatabaseCache`), sessions. No Redis, no Celery, no SQLite fallback in tests when RLS is on.
- **One env-driven `settings.py`** (django-environ) plus `settings_test.py` that imports it. `env.bool("DEBUG")`, never `config.get("DEBUG")` — the string `"False"` is truthy (appsfolio bug).
- **Refuse to boot in prod without secrets.** Dummy values only inside the Docker `collectstatic` step.
- **`MAILERS` (Django 6.1), not `EMAIL_BACKEND`**. The old settings are deprecated, and 6.1's deploy check rejects dev-only mail backends.
- **`STORAGES` dict, not `STATICFILES_STORAGE`** — Django ≥5.1 ignores the old setting silently (meetingsignals bug).
- **Product name and domain are settings, never literals.** Everything else (hosts, cookie domains, CSRF origins, from-address, WebAuthn RP) is derived.
- **`/ht/` does `SELECT 1` and returns 503 on failure** without leaking the error; it is exempt from SSL redirect, Sentry traces and access logs.
- **Why-comments.** Comments explain the reason and name the incident. Deliberate simplifications carry a `ponytail:` comment naming the ceiling and upgrade path.
- **Meta-tests guard categories of mistake** (every tenant table has a policy, every help anchor exists, generated files have no drift) rather than one instance.
- **A CI test+lint gate runs before any deploy.** Four of five repos lacked this; don't copy the gap.
- **Pin third-party GitHub Actions by SHA with a version comment; pin CDN/vendored JS exactly.**
- **Prod never runs `:latest`** and never rebuilds — it promotes the digest that ran on test.

## Composes with

- `gxp-doc` — controlled documents (URS, RA, VP, SOPs) for GxP apps.
- `design-md` — the app's `DESIGN.md` design tokens.
- `uv` — ensures uv is installed before scaffolding.
