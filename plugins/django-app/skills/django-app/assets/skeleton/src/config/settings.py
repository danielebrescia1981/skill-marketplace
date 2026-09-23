"""MyApp settings — one file for dev, test and prod, driven by environment variables.

PRODUCT_NAME and BASE_DOMAIN are the only literals. Hosts, cookie domains, CSRF
origins and the sender address are all derived from them; a product name or
domain hardcoded anywhere else is a bug.
"""

from email.utils import formataddr
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP
import environ

from config.app_list import LOCAL_APPS

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # repo root
env = environ.Env()
environ.Env.read_env(env("ENV_FILE", default=str(BASE_DIR / ".env")))

APP_ENVIRONMENT = env("APP_ENVIRONMENT", default="dev")  # dev | test | prod
DEBUG = env.bool("DEBUG", default=APP_ENVIRONMENT == "dev")
APP_VERSION = env("APP_VERSION", default="dev")

if APP_ENVIRONMENT == "prod" and DEBUG:
    raise ImproperlyConfigured("DEBUG must be off in prod.")


def _required(name: str, dev_default: str = "") -> str:
    """A secret that must be set whenever DEBUG is off. Refuse to boot rather than run insecure."""
    value = env(name, default="")
    if value:
        return value
    if DEBUG:
        return dev_default
    raise ImproperlyConfigured(f"{name} must be set when DEBUG is off.")


SECRET_KEY = _required("SECRET_KEY", "django-insecure-dev-only")

# --- Identity ---------------------------------------------------------------
PRODUCT_NAME = env("PRODUCT_NAME", default="MyApp")
BASE_DOMAIN = env("BASE_DOMAIN", default="myapp.localhost")  # may carry a port in dev
BASE_DOMAIN_NAME = BASE_DOMAIN.split(":")[0]
SITE_URL = env("SITE_URL", default=f"https://{BASE_DOMAIN}")

# Loopback always allowed so the container HEALTHCHECK can reach /ht/.
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[BASE_DOMAIN_NAME, f".{BASE_DOMAIN_NAME}"]) + [
    "127.0.0.1",
    "localhost",
]
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS", default=[f"https://{BASE_DOMAIN}", f"https://*.{BASE_DOMAIN_NAME}"]
)
# [tenant]
TENANT_BASE_DOMAINS = [BASE_DOMAIN_NAME, "localhost"]
# [/tenant]

# --- Apps -------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "crispy_forms",
    "crispy_tailwind",
    "django_htmx",
    "procrastinate.contrib.django",
    # [tenant]
    "django_rls",
    # [/tenant]
    *LOCAL_APPS,
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # [tenant]
    "tenants.middleware.TenantRLSMiddleware",  # after auth: RLS context comes from request.user
    # [/tenant]
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

if DEBUG:
    try:
        import django_browser_reload  # noqa: F401  (dev group only)

        INSTALLED_APPS += ["django_browser_reload"]
        MIDDLEWARE += ["django_browser_reload.middleware.BrowserReloadMiddleware"]
    except ImportError:
        pass

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
SITE_ID = 1

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csp",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.site",
            ],
        },
    },
]

# --- Database ---------------------------------------------------------------
# [tenant]
# Two roles (scripts/create-db-roles.sh): `default` = myapp_app, RLS applies;
# `admin` = myapp_admin, BYPASSRLS + table owner (migrations, admin site, cross-tenant jobs).
DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://myapp_app:myapp_app@localhost:__DB_PORT__/myapp"),
    "admin": env.db("ADMIN_DATABASE_URL", default="postgres://myapp_admin:myapp_admin@localhost:__DB_PORT__/myapp"),
}
for _alias in ("default", "admin"):
    DATABASES[_alias]["ENGINE"] = "django_rls.backends.postgresql"
    DATABASES[_alias]["CONN_MAX_AGE"] = 0  # no RLS context can survive on a reused connection
DATABASE_ROUTERS = ["config.db_router.RLSRouter"]
DJANGO_RLS = {
    # Both receivers act on django.db.connection (the app alias) whichever alias fired:
    # auto-enable would attempt DDL as the app role; connect-reset would wipe the app
    # connection's tenant whenever an admin-alias connection opens. Policies come from
    # explicit migrations; the reset is tenants.rls.reset_rls_on_new_connection.
    "AUTO_ENABLE_RLS": False,
    "RESET_CONTEXT_ON_CONNECT": False,
}
# [/tenant]
# [!tenant]
DATABASES = {"default": env.db("DATABASE_URL", default="postgres://myapp:myapp@localhost:__DB_PORT__/myapp")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=0)
# [/!tenant]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Postgres-backed cache: shared across workers, so rate limits and single-use
# tokens mean what they say. LocMem would give each worker its own copy.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "django_cache"}}

# --- Auth -------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_CONFIRM_EMAIL_ON_GET = False  # mail scanners pre-fetch GET links
ACCOUNT_LOGOUT_ON_GET = False  # a GET must not change state
ACCOUNT_EMAIL_SUBJECT_PREFIX = "" if APP_ENVIRONMENT == "prod" else f"[{PRODUCT_NAME} {APP_ENVIRONMENT.upper()}] "
LOGIN_REDIRECT_URL = "/"

# --- Security ---------------------------------------------------------------
HARDENED = env.bool("SECURITY_HARDENING", default=not DEBUG)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=HARDENED)
SECURE_REDIRECT_EXEMPT = [r"^ht/$"]
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000 if HARDENED else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = HARDENED
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = HARDENED
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"  # Strict breaks SSO callbacks and emailed links
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=8 * 3600 if HARDENED else 14 * 86400)
CSRF_COOKIE_SECURE = HARDENED
# [tenant]
# Shared across tenant subdomains so login survives the canonical-subdomain redirect.
SESSION_COOKIE_DOMAIN = env("SESSION_COOKIE_DOMAIN", default=f".{BASE_DOMAIN_NAME}")
CSRF_COOKIE_DOMAIN = env("CSRF_COOKIE_DOMAIN", default=f".{BASE_DOMAIN_NAME}")
# [/tenant]
_csp = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF, CSP.NONCE],
    "img-src": [CSP.SELF, "data:"],
    "frame-ancestors": [CSP.NONE],
    "form-action": [CSP.SELF],
}
# Report-only until the app's pages are clean under it; then set CSP_ENFORCE=true.
if env.bool("CSP_ENFORCE", default=False):
    SECURE_CSP = _csp
else:
    SECURE_CSP_REPORT_ONLY = _csp

# --- Static, media, storage -------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# [help]
STATICFILES_DIRS += [("help", BASE_DIR / "help_site")] if (BASE_DIR / "help_site").exists() else []
# [/help]
MEDIA_URL = "/media/"
MEDIA_ROOT = env.path("MEDIA_ROOT", default=BASE_DIR / "media")
STORAGES = {
    # USE_S3 → "storages.backends.s3.S3Storage" (add django-storages); see references/tasks-email.md
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- Tasks & email ----------------------------------------------------------
PROCRASTINATE_IMPORT_PATHS = ["config.tasks"]
# Django 6.1 MAILERS: `default` queues every message on Procrastinate (requests never wait
# on SES; failures retry); the worker sends through `transport` (config.tasks.send_email_task).
EMAIL_ASYNC = env.bool("EMAIL_ASYNC", default=True)
if APP_ENVIRONMENT in ("test", "prod"):
    _transport = {"BACKEND": "django_ses.SESBackend"}
else:  # Mailpit in dev
    _transport = {
        "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
        "OPTIONS": {"host": env("EMAIL_HOST", default="localhost"), "port": env.int("EMAIL_PORT", default=1025)},
    }
MAILERS = {
    "default": {"BACKEND": "config.email_backends.ProcrastinateEmailBackend"} if EMAIL_ASYNC else _transport,
    "transport": _transport,
}
MAIL_DOMAIN = env("MAIL_DOMAIN", default=f"mail.{BASE_DOMAIN_NAME}")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=formataddr((PRODUCT_NAME, f"noreply@{MAIL_DOMAIN}")))
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# --- Forms ------------------------------------------------------------------
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# --- i18n -------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Logging & errors -------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        # Health checks every few seconds would drown the request log.
        "skip_health": {"()": "django.utils.log.CallbackFilter", "callback": lambda r: "/ht/" not in r.getMessage()},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "filters": ["skip_health"]}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
}

SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN and APP_ENVIRONMENT in ("test", "prod"):
    import sentry_sdk

    def _traces_sampler(ctx):
        path = (ctx.get("wsgi_environ") or {}).get("PATH_INFO", "")
        return 0 if path.startswith(("/ht/", "/metrics")) else 0.1

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=APP_ENVIRONMENT,
        release=f"myapp@{APP_VERSION}",
        send_default_pii=False,
        traces_sampler=_traces_sampler,
    )
