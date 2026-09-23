# Tenancy — shared schema + Postgres row-level security (django-rls)

**Load:** only when the app is tenant-based (Q1 = yes). **Do this before the first domain model.** **Assets:** `assets/skeleton/src/tenants/`, `src/config/db_router.py`, `scripts/create-db-roles.sh`, `tests/test_rls.py`, and the `[tenant]` blocks across the skeleton.

Proven in eqms and gxpsign; appsfolio learned it the hard way (`PLAN_RLS_SECURITY.md`: the app role was SUPERUSER + BYPASSRLS, so every policy was inert and one tenant's data showed up for another).

## The model in one paragraph

One database, one schema. Every tenant-scoped table has a `tenant_id` column and an RLS policy `tenant_id = current_setting('rls.tenant_id', true)`. Web traffic connects as an **app role that cannot bypass RLS** and doesn't own the tables; the middleware sets `rls.tenant_id` **transaction-locally** from the *authenticated user's* tenant. Migrations, the Django admin and cross-tenant workers use a second **admin role** (BYPASSRLS, table owner) via a second DB alias. With no tenant set, the policy matches nothing — **fail closed**.

## Two roles, two aliases

`scripts/create-db-roles.sh` (mounted into `docker-entrypoint-initdb.d`) creates:

- `myapp_admin` — `LOGIN BYPASSRLS CREATEDB`, owns the database, schema and tables. Needs CREATEDB so pytest can build the test DB.
- `myapp_app` — `LOGIN NOBYPASSRLS`, DML only, plus `ALTER DEFAULT PRIVILEGES FOR ROLE myapp_admin … GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO myapp_app` so tables created by later migrations are usable at once.

It runs once per fresh volume. On an existing volume or in prod, run its SQL by hand, and **assert the app role with a startup check**:

```python
# tenants/checks.py — registered with @register(deploy=True) and run by `manage.py check --deploy` in CI/deploy
cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
if any(cursor.fetchone()):
    errors.append(Error("default DB alias can bypass RLS — every policy is inert", id="tenants.E001"))
```

Settings:

```python
DATABASES = {"default": env.db("DATABASE_URL"), "admin": env.db("ADMIN_DATABASE_URL")}
for _alias in ("default", "admin"):
    DATABASES[_alias]["ENGINE"] = "django_rls.backends.postgresql"
    DATABASES[_alias]["CONN_MAX_AGE"] = 0      # no context can survive on a reused connection
DATABASE_ROUTERS = ["config.db_router.RLSRouter"]
DJANGO_RLS = {
    # Both receivers act on django.db.connection (the app alias) whatever alias fired them:
    # auto-enable tries DDL as the app role, and connect-reset wipes the app connection's
    # tenant when an admin-alias connection opens. Policies come from explicit migrations;
    # the reset is our own receiver (tenants/rls.py).
    "AUTO_ENABLE_RLS": False,
    "RESET_CONTEXT_ON_CONNECT": False,
}
```

(django-rls 0.4.x has no settings for these; eqms/gxpsign disconnect the receivers in `TenantsConfig.ready()`. django-rls ≥ 2.0 supports Django 6 directly, so no `override-dependencies` either.)

## Router (`config/db_router.py`)

The skeleton's `src/config/db_router.py` is a condensed eqms `RLSRouter`. What it does:

- `ADMIN_APPS = {"admin", "contenttypes", "sessions", "sites", "auth", "procrastinate", "guardian"}` → always `admin`. These are platform-wide or read before a tenant exists.
- `allow_migrate` returns `db == "admin"`. The app alias never changes schema. **Always `migrate --database=admin`** (the justfile's `MIGRATE_DB` does this).
- While a migration runs (a `pre_migrate`/`post_migrate` signal pair maintains a `_MIGRATING` set), *all* ORM access goes to `admin`, so third-party RunPython data migrations work without `.using()`.
- A thread-local `_ADMIN_REQUEST` flag, set by the middleware only for staff on `/admin/`, routes everything to `admin`. Without it the Django admin sees one tenant, and deleting a tenant fails at COMMIT because the cascade can't see the RLS-protected children. **Release it in `finally`** or the next request on that thread inherits BYPASSRLS.
- `Tenant` and `User` stay on `default`, with no RLS. Moving them to `admin` gives cross-alias FKs that break test teardown.

## Models

```python
# tenants/models.py
class Tenant(TenantSSOMixin, models.Model):          # [sso] mixin only with damsso
    slug = models.SlugField(primary_key=True, max_length=63, validators=[subdomain_validator])
    name = models.CharField(max_length=200)
    # Doubles as the subdomain; a text PK keeps the policy a plain text compare.

class User(AbstractUser):                             # see foundation.md § User
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, null=True, related_name="users")
    role = models.CharField(choices=Role.choices, default=Role.USER)   # org_owner | org_admin | user | reader

class SlugTenantPolicy(BasePolicy):                   # same module
    def __init__(self, name, tenant_field="tenant", **kw):
        self.tenant_field = tenant_field
        super().__init__(name, **kw)
    def get_sql_expression(self):
        # No empty-tenant bypass: unset → no rows. Cross-tenant access is the admin role's job.
        return f"{self.tenant_field}_id = current_setting('rls.tenant_id', true)"

class TenantIsolatedModel(RLSModel):
    """Declares the policy. Does NOT create it — the app's *_rls_enable migration does."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="%(class)s_items", db_index=True)
    class Meta:
        abstract = True
        rls_policies = [SlugTenantPolicy("tenant_isolation", tenant_field="tenant")]
    def save(self, *a, **kw):
        if not self.tenant_id:
            raise ValueError(f"{type(self).__name__} saved without a tenant")
        super().save(*a, **kw)
```

One user belongs to one tenant (eqms, gxpsign, appsfolio). If users really need multiple orgs, make that explicit with a membership model and an "active tenant" in the session, validated on every request. Don't start there.

## Policy migrations (explicit, per app)

After `makemigrations` creates the tables, add `NNNN_rls_enable.py`:

```python
from django.db import migrations
from django_rls.migration_operations import CreatePolicy, EnableRLS
from tenants.models import SlugTenantPolicy

def _policy():
    return SlugTenantPolicy("tenant_isolation", tenant_field="tenant")

_MODELS = ["Document", "DocumentVersion",
           "HistoricalDocument"]          # simple-history copies tenant FKs — list the Historical* tables too

class Migration(migrations.Migration):
    dependencies = [("documents", "0001_initial")]
    operations = [op for m in _MODELS for op in (EnableRLS(m), CreatePolicy(m, _policy()))]
```

- M2M through-tables have no `tenant_id`. Either give the through-model a tenant, or accept (with a `ponytail:` comment) that a cross-tenant read yields only ID pairs that resolve to nothing because both ends are protected. Or use a subquery policy: `view_id IN (SELECT id FROM app_view WHERE tenant_id = current_setting('rls.tenant_id', true))`.
- `FORCE ROW LEVEL SECURITY` only matters when the querying role owns the table. It won't if the app role is set up as above. `manage.py audit_rls` (django-rls 2.x) will still flag it; the role check above is the stronger guarantee.

## Context (`tenants/rls.py`)

```python
def set_rls_tenant(tenant_id: str) -> None:
    with connection.cursor() as c:                     # must be inside transaction.atomic()
        c.execute("SELECT set_config('rls.tenant_id', %s, true)", [tenant_id])   # true = transaction-local

@contextmanager
def tenant_context(tenant_id):                         # workers, commands, tests; reentrant
    old = get_current_tenant_id()
    set_current_tenant_id(tenant_id); set_rls_tenant(tenant_id) if tenant_id else clear_rls_tenant()
    try: yield
    finally:
        set_current_tenant_id(old); set_rls_tenant(old) if old else clear_rls_tenant()

def reset_rls_on_new_connection(sender, connection, **kw):   # connection_created receiver
    if connection.vendor == "postgresql":
        with connection.cursor() as c:                  # *this* connection, not django.db.connection
            c.execute("SELECT set_config('rls.tenant_id', '', false)")
```

Gotcha: inside a transaction, `RESET` leaves the setting as `''`, not NULL. Any policy with a "no context" bypass must treat `''` like NULL. Ours has no bypass, so `''` matches nothing. That's the point.

Workers: each Procrastinate task that touches tenant data takes `tenant_id` as an argument and runs its body in `with transaction.atomic(), tenant_context(tenant_id):`. Never let a task infer the tenant.

## Middleware (`tenants/middleware.py`)

Place it after `AuthenticationMiddleware`. The skeleton's `src/tenants/middleware.py` (condensed from eqms `TenantRLSMiddleware`). Its contract:

1. The subdomain is resolved **for display and canonical URLs only; it never grants access.** Access comes from `request.user.tenant`.
2. A logged-in user on the wrong subdomain gets redirected to their own on page loads. HTMX requests aren't redirected; they're served under the user's own tenant.
3. `with transaction.atomic(): set_rls_tenant(tenant.slug); response = self.get_response(request)`. For a response ≥ 500, call `transaction.set_rollback(True)` (appsfolio), because inner middleware has already turned the exception into a response.
4. `TENANT_EXEMPT_PATHS`: an entry ending in `/` is a prefix, anything else is exact. A loose `/mcp` prefix would silently exempt `/mcpanything`. Typical entries: `/`, `/admin/`, `/accounts/`, `/sso/`, `/static/`, `/ht/`, `/help/`, `/ses/events/`, `/api/`, `/.well-known/`.
5. `OperationalError`/`InterfaceError` → 503, not 500.
6. Tenant base domains come from `BASE_DOMAIN`. `SESSION_COOKIE_DOMAIN = f".{BASE_DOMAIN_NAME}"` so login survives the subdomain redirect.

Token-authenticated API calls set the context from the token's user in the auth class (api-mcp.md), not from the host.

## Escape hatch

`.using("admin")` is for code that genuinely has no tenant context: the cross-tenant signer flow, platform staff tools, the SSO login lookup. It's never a way to "make a query work". CLAUDE.md says so. Grep for `.using("admin")` in review; each use carries a comment explaining why.

## Tests (Postgres only)

- No SQLite fallback: testing isolation on SQLite tests nothing.
- `settings_test.py`: `DATABASES["default"]["TEST"] = {"MIRROR": "admin"}` so the runner builds one test DB (as admin) and `default` stays RLS-subject. `TEST_DB_NAME` comes from env for parallel runs.
- `conftest.py` (asset `[tenant]` blocks):
  - `pytest_collection_modifyitems` merges `databases=["default", "admin"]` into every `django_db` marker.
  - A session fixture GRANTs DML on the test DB to the app role. The runner created every table as admin.
  - An autouse `clean_rls_context` clears the context before and after each test. `SET LOCAL` survives savepoint rollback inside pytest-django's outer transaction.
- Per model: `test_rls_hides_another_tenants_<model>` — no context → 0 rows; tenant A sees only A; admin alias sees all; creating a row for tenant B under A's context raises `ProgrammingError` (the policy's implicit WITH CHECK). **Any test that compares the `default` and `admin` aliases needs `django_db(transaction=True)`**: they are separate connections, so admin can't see rows default hasn't committed. Worked example:
  ```python
  @pytest.mark.django_db(transaction=True)
  def test_rls_hides_another_tenants_notes(tenant_factory):
      a, b = tenant_factory(), tenant_factory()
      with transaction.atomic(), tenant_context(a.slug):
          Note.objects.create(tenant=a, text="a's")
      with transaction.atomic(), tenant_context(b.slug):
          Note.objects.create(tenant=b, text="b's")
          assert list(Note.objects.values_list("text", flat=True)) == ["b's"]
      assert Note.objects.count() == 0                 # no context → fail closed
      assert Note.objects.using("admin").count() == 2  # BYPASSRLS sees all
  ```
- **The meta-test** (eqms `tests/test_hardening.py`) covers every managed model with a `tenant` field. Its table must show `relrowsecurity` and at least one `pg_policy`. Exempt list: `{"<app>_user"}` (read before tenant context exists). This catches the migration you forgot, including `Historical*` tables.
- Optional static guard (appsfolio `scripts/check_tenant_scope.py` pre-commit hook): an AST lint flagging `Model.objects.filter(...)` on sensitive models with no tenant filter, with a baseline file so only new offenders fail. Belt and braces for code paths that run on the admin alias.

## Deploy

- Test and prod each get their own `myapp_app` / `myapp_admin` credentials. The app container gets both URLs.
- Deploy runs `migrate --database=admin`, then `check --deploy`, which includes the role check.
- Data residency, if promised: a `DEPLOYMENT_REGION` setting plus a system check asserting the storage bucket region matches (eqms `tenants/checks.py`).
