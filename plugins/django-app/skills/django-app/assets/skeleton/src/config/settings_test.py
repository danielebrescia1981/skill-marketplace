"""Test settings: the real settings, with only what a test run can't live with changed.

Imports settings rather than mirroring them, so middleware, RLS and security
posture under test are the ones that ship.
"""

import os

os.environ.setdefault("SENTRY_DSN", "")

from config.settings import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MAILERS = {alias: {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"} for alias in ("default", "transport")}
STORAGES = {**STORAGES, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
WHITENOISE_AUTOREFRESH = True  # serve via finders: no collectstatic needed, no missing-STATIC_ROOT warning

# [tenant]
# Only `admin` creates the test DB (it has CREATEDB and owns the schema). `default`
# mirrors it — same database, app role — so queries there stay RLS-subject in tests.
# The shared TEST NAME stops the runner treating admin as depending on default.
# TEST_DB_NAME lets parallel runs each own a database.
_TEST_DB_NAME = env("TEST_DB_NAME", default="test_myapp")
DATABASES["admin"]["TEST"] = {"NAME": _TEST_DB_NAME}
DATABASES["default"]["TEST"] = {"MIRROR": "admin", "NAME": _TEST_DB_NAME}
# [/tenant]
