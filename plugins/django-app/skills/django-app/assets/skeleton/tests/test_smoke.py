import re

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.management import call_command
from django.test import override_settings
import pytest


@pytest.mark.django_db
def test_health_check_answers(client):
    response = client.get("/ht/")
    assert response.status_code == 200
    assert response.content == b"ok"


@pytest.mark.django_db
def test_home_renders(client):
    assert client.get("/").status_code == 200


@pytest.mark.django_db
def test_change_password_well_known_redirects(client):
    response = client.get("/.well-known/change-password")
    assert response.status_code == 302


@pytest.mark.django_db
def test_login_page_renders(client):
    assert client.get("/accounts/login/").status_code == 200


@pytest.mark.django_db
def test_ensure_superuser_is_idempotent_and_can_log_in(client):
    call_command("ensure_superuser", "root@example.com", password="correct-horse-battery")
    call_command("ensure_superuser", "root@example.com", password="correct-horse-battery-2")
    assert client.login(email="root@example.com", password="correct-horse-battery-2")


@pytest.mark.security
@override_settings(
    DEBUG=False,
    SECURE_SSL_REDIRECT=True,
    SECURE_HSTS_SECONDS=31536000,
    SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
    SECURE_HSTS_PRELOAD=True,
    SESSION_COOKIE_SECURE=True,
    CSRF_COOKIE_SECURE=True,
    SECRET_KEY="x" * 60 + "-a-long-random-looking-production-secret",
    MAILERS={
        "default": {"BACKEND": "config.email_backends.ProcrastinateEmailBackend"},
        "transport": {"BACKEND": "django_ses.SESBackend"},
    },
)
def test_deploy_checks_are_clean():
    # Raises SystemCheckError on any deploy warning or error.
    call_command("check", "--deploy", "--fail-level", "WARNING")


# Built by `just css` / the Docker css stage, so absent in a fresh checkout.
BUILT_STATIC = {"css/output.css"}


def test_every_static_file_referenced_by_templates_exists():
    """Tests use plain StaticFilesStorage; in prod a missing file is a manifest error: 500 on every page."""
    refs = set()
    for path in (settings.BASE_DIR / "templates").rglob("*.html"):
        refs |= set(re.findall(r"{%\s*static\s+['\"]([^'\"]+)['\"]", path.read_text()))
    missing = sorted(r for r in refs - BUILT_STATIC if not finders.find(r))
    assert not missing, f"templates reference missing static files (run `just vendor`?): {missing}"
