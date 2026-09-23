# MyApp

<!-- Keep this file short and true. When a change makes a line here wrong, fix it in the same commit. -->

## Shape

Scaffolded with the `django-app` skill. Features on:
<!-- [tenant] -->
- **Tenant-based**: shared schema, Postgres RLS via django-rls (two DB roles).
<!-- [/tenant] -->
<!-- [!tenant] -->
- Not tenant-based: data is scoped per user in queries.
<!-- [/!tenant] -->
- SSO: none · GxP: no · Billing: no · API/MCP: no  <!-- update as modules are added -->

## Commands

- `just setup` once, then `just dev`: https://myapp.localhost/ (Mailpit at http://localhost:8025/)
- `just test`, `just check` (lint + Django checks + migration drift). Run tests via `just`, not bare `pytest`.
- Always `uv run …`; add deps with `uv add X` / `uv add --group dev X`.

## Rules

- Branches: work on `dev`; promote `dev → test` (auto-deploys test) → `main` (manual prod deploy). Never commit to `test` or `main` directly.
- `PRODUCT_NAME` and `BASE_DOMAIN` are the only literals; a product name or domain hardcoded elsewhere is a bug.
- Postgres for everything: queue (Procrastinate), cache, sessions. No Redis.
- New models: UUIDv7 PK (`db_default=UUIDv7()`). Test newness with `self._state.adding`, never `if self.pk`.
- Comments say *why*. Deliberate simplifications get a `ponytail:` comment naming the ceiling and upgrade path.
<!-- [tenant] -->
- Every tenant-scoped model inherits `tenants.models.TenantIsolatedModel`. **Inheriting the base does not create the policy; the migration does.** Add `EnableRLS` + `CreatePolicy` in an `NNNN_rls_enable` migration (Historical* tables too). `tests/test_rls.py` fails otherwise.
- Migrations run as the admin role: `just migrate` (= `migrate --database=admin`).
- `.using("admin")` only where there's genuinely no tenant context, with a comment saying why. Never to "make a query work".
- Tasks that touch tenant data take `tenant_id` and run inside `tenants.rls.tenant_context`.
<!-- [/tenant] -->

## Where things are

- `docs/`: engineering docs (ARCHITECTURE, DEPLOYMENT, …). `help/`: user-facing docs served at `/help/`.
- `TODO.md`: agent-doable work. `LAUNCH.md`: human-only launch tasks.
- Deploys: `.github/workflows/`; compose stacks live in the `devmo_apps` repo.

## Things that mislead

<!-- Add gotchas here as you hit them: things that look wrong but aren't, or look fine but bite. -->
