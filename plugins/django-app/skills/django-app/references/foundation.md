# Foundation — layout, dependencies, settings, user model

**Load:** always in Create mode. **Assets:** `assets/skeleton/pyproject.toml`, `assets/skeleton/src/config/settings.py`, `settings_test.py`, `assets/skeleton/dot-env.example`.

## Layout (src/)

```
myapp/
├── manage.py                # sys.path.insert(0, BASE_DIR / "src")
├── pyproject.toml  uv.lock  .python-version  justfile
├── Dockerfile  docker-compose.yml  .dockerignore  .env.example
├── CLAUDE.md  README.md  TODO.md  [LAUNCH.md]
├── src/
│   ├── config/              # project package: cross-cutting code only
│   │   ├── settings.py  settings_test.py  [settings_e2e.py]
│   │   ├── urls.py  wsgi.py  asgi.py
│   │   ├── app_list.py      # LOCAL_APPS — the one place apps are registered
│   │   ├── nav.py           # single nav source for templates
│   │   ├── context_processors.py  middleware.py  logging_config.py
│   │   ├── procrastinate.py  tasks.py  email_backends.py   (tasks-email.md)
│   │   └── db_router.py     # [tenant]
│   ├── accounts/  or tenants/   # User (+ Tenant when tenant-based)
│   └── <domain apps>/       # models, views, forms, urls, api.py (service layer), tasks.py
├── templates/               # project-level: <app>/<object>_<action>.html, <app>/partials/_x.html
├── static/{css,js,images,vendor,fonts}
├── help/                    # user docs source (frontend.md § help)
├── docs/                    # engineering docs (repo-management.md)
├── scripts/                 # db init, one-off ops
└── tests/                   # flat tests/test_<module>.py (+ tests/e2e/)
```

Why `src/`: eqms and gxpsign (the two newest) use it; it keeps `manage.py`, tooling and docs out of the import path. `manage.py` inserts `src/`; the Dockerfile sets `PYTHONPATH=/app/src`; pytest uses `pythonpath = ["src"]`.

Per-app service layer: `api.py` holds the functions views, tasks, the REST API and MCP tools all call. Views stay thin; business rules live once.

## Dependencies (uv + hatchling)

- `requires-python = ">=3.14"`, `Django>=6.1,<7.0` (6.1 for `MAILERS`; see tasks-email.md), `psycopg[binary]` (psycopg 3), Postgres 18 (native `uuidv7()`).
- `[dependency-groups] dev` for dev tools; `uv add --group dev X`. Always `uv run …`, never bare `python`.
- Git-sourced house libraries pin a tag: `damsso = { git = "https://github.com/wshayes/damsso", tag = "vX.Y.Z" }`, with a commented local-editable line for hacking on it.
- Every non-obvious pin carries a comment saying why.
- **django-rls ≥ 2.0 supports Django 6** — the `[tool.uv] override-dependencies = ["Django>=6.0,<7.0"]` hack in older repos was for 0.4.x. Check `uv pip show django-rls` before copying it.

Runtime baseline (add module deps as modules load):

```
django, django-environ, psycopg[binary], gunicorn, whitenoise[brotli],
django-allauth, django-crispy-forms, crispy-tailwind, django-htmx,
procrastinate[django], django-ses[events], sentry-sdk[django], loguru
```

Dev: `pytest, pytest-django, pytest-mock, factory-boy, ruff, mypy, django-debug-toolbar, django-browser-reload, watchfiles, pre-commit`. Add `playwright`/`pytest-playwright` when e2e starts.

Ruff (all repos agree):

```toml
[tool.ruff]
line-length = 120
extend-exclude = ["*/migrations/*"]
[tool.ruff.lint]
select = ["I"]
extend-select = ["E", "F", "W", "UP"]
[tool.ruff.lint.isort]
force-sort-within-sections = true
known-first-party = ["config"]           # + each app
[tool.ruff.lint.per-file-ignores]
"src/config/settings*.py" = ["E402"]
```

mypy with `check_untyped_defs`, excluding migrations — informational until the codebase is clean, then gate it.

## Settings

One env-driven `settings.py` for dev/test/prod; see `assets/skeleton/src/config/settings.py`. Rules:

- `environ.Env.read_env(env("ENV_FILE", default=BASE_DIR / ".env"))`.
- `APP_ENVIRONMENT = env("APP_ENVIRONMENT", default="dev")  # dev | test | prod` — separate from `DEBUG`. Sentry, email subject prefixes (`[MyApp TEST]`) and seed commands key off it.
- **Required secrets fail closed** (meetingsignals pattern):
  ```python
  def _required(name, dev_default):
      value = env(name, default="")
      if value: return value
      if DEBUG: return dev_default
      raise ImproperlyConfigured(f"{name} must be set when DEBUG is off.")
  ```
- **Derive, don't repeat.** `PRODUCT_NAME` and `BASE_DOMAIN` are the only literals; `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, cookie domains, `DEFAULT_FROM_EMAIL` (via `formataddr`), `SITE_URL`, WebAuthn RP ID all derive. A literal product name elsewhere in code is a bug (eqms CLAUDE.md rule).
- Loopback always in `ALLOWED_HOSTS` so the container `HEALTHCHECK` works.
- `LOCAL_APPS` imported from `config/app_list.py` so `settings.py` and `settings_test.py` can't drift.
- `STORAGES = {"default": …, "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}`. `USE_S3` flips only `default` (R2/S3 via django-storages).
- `CACHES` = `DatabaseCache` (`createcachetable` in a migration or setup). Comment: LocMem gives each worker its own copy and silently multiplies every rate limit.
- `CONN_MAX_AGE = 0` (required with RLS; fine without). Psycopg 3 pool via `OPTIONS["pool"]` only if measured need.
- Sentry initialises only when `SENTRY_DSN and APP_ENVIRONMENT in ("test", "prod")`, `send_default_pii=False`, `release=f"myapp@{APP_VERSION}"`, a `traces_sampler` that returns 0 for `/ht/` and `/metrics`.
- `APP_VERSION = env("APP_VERSION", default="dev")` → context processor → footer shows the running version.
- `settings_test.py`: `from .settings import *` then override (MD5 hasher, console email, rate limits off, `SENTRY_DSN=""`). Importing, not mirroring — standalone mirrors in eqms/gxpsign drift.

## User model

Custom from day one, email as username:

```python
class User(AbstractUser):
    id = models.UUIDField(primary_key=True, db_default=UUIDv7(), editable=False)
    username = None
    email = models.EmailField(unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()          # create_user/create_superuser keyed on email
```

- `UUIDv7` is a three-line `Func` (Django has no built-in), in a shared module such as `config/db.py`; needs Postgres 18. Use it for domain-model PKs too:
  ```python
  class UUIDv7(Func):
      """PostgreSQL 18+ uuidv7() — time-ordered UUID primary keys."""
      function = "uuidv7"
      output_field = models.UUIDField()
  ```
- **The `db_default` PK trap:** with `db_default`, `self.pk` is a `DatabaseDefault` sentinel (truthy) until saved. Code that asks "is this new?" must use `self._state.adding`, never `if self.pk`. ModelForms that branch on `instance.pk` misbehave. eqms guards it with `tests/test_create_forms.py`.
- Management command `ensure_superuser` (idempotent: create or reset password, **and create the allauth `EmailAddress(verified=True, primary=True)` row**, otherwise the superuser can't log in with mandatory verification).

## URLs

```python
urlpatterns = [
    path("ht/", views.health_check),                     # first: SELECT 1 → 200 / 503
    path(".well-known/change-password", RedirectView.as_view(pattern_name="account_change_password")),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    ...
]
handler404 = "config.views.page_not_found"
handler500 = "config.views.server_error"                 # passes sentry_event_id to the template
```

Health check:

```python
def health_check(request):
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
    except Exception:
        # Log, don't return: psycopg errors carry host and user names.
        logger.exception("health check failed")
        return HttpResponse("unhealthy", status=503)
    return HttpResponse("ok")
```

Optionally `/ping/` (no DB) for an external uptime monitor.

## Auth baseline (allauth, email only)

```python
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_CONFIRM_EMAIL_ON_GET = False   # link scanners pre-fetch GET links
ACCOUNT_LOGOUT_ON_GET = False          # a GET must not change state
ACCOUNT_ADAPTER = "accounts.adapters.AccountAdapter"
```

Password `MinimumLengthValidator` min 12. Override allauth templates under `templates/account/`.

Alternative for low-stakes, buyer-only admin surfaces: a hand-rolled magic link (refractions `manager/auth.py`) — `TimestampSigner(salt=…)`, 15-minute expiry, single-use via the cache, **verify and spend in separate steps** so link-preview bots don't burn the link. Default to allauth.

## Realtime (only if Q6 = yes)

Channels + `channels-redis`, served by uvicorn (`config.asgi`); Redis is the only permitted non-Postgres service. `AllowedHostsOriginValidator(AuthMiddlewareStack(URLRouter(...)))`, and each consumer's `connect()` authorises membership — knowing a room code must not be enough to listen (meetingsignals `consumers.py`). Without realtime, serve WSGI with gunicorn.
