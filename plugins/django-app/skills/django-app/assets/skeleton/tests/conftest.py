import factory
from factory.django import DjangoModelFactory
import pytest


# [tenant]
def pytest_collection_modifyitems(config, items):
    """Give every DB test both aliases: `default` (app role, RLS applies) and `admin` (BYPASSRLS)."""
    for item in items:
        marker = next(iter(item.iter_markers(name="django_db")), None)
        if marker is None:
            continue
        kwargs = dict(marker.kwargs)
        kwargs["databases"] = sorted(set(kwargs.get("databases") or ("default",)) | {"default", "admin"})
        item.own_markers = [m for m in item.own_markers if m.name != "django_db"]
        item.add_marker(pytest.mark.django_db(*marker.args, **kwargs))


@pytest.fixture(autouse=True, scope="session")
def grant_app_role_on_test_db(django_db_setup, django_db_blocker):
    """The runner built the test DB as admin, so the app role owns nothing yet: grant it DML."""
    from django.db import connections

    connections["default"].close()  # it may still point at the dev DB from before the runner repointed it
    with django_db_blocker.unblock(), connections["admin"].cursor() as cursor:
        cursor.execute(
            "GRANT USAGE ON SCHEMA public TO myapp_app;"
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO myapp_app;"
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO myapp_app;"
        )
    yield
    connections.close_all()


@pytest.fixture(autouse=True)
def clean_rls_context(request):
    """SET LOCAL survives savepoint rollback inside pytest-django's outer transaction: reset around each test."""
    if "django_db" not in {m.name for m in request.node.iter_markers()}:
        yield
        return
    from tenants.rls import clear_rls_tenant

    clear_rls_tenant()
    yield
    try:
        clear_rls_tenant()
    except Exception:
        pass  # transaction broken by the test; nothing to clear


@pytest.fixture
def tenant_factory():
    from tenants.models import Tenant

    class TenantFactory(DjangoModelFactory):
        class Meta:
            model = Tenant

        slug = factory.Sequence(lambda n: f"org{n}")
        name = factory.Sequence(lambda n: f"Org {n}")

    return TenantFactory


# [/tenant]
@pytest.fixture
def user_factory():
    from django.contrib.auth import get_user_model

    class UserFactory(DjangoModelFactory):
        class Meta:
            model = get_user_model()

        email = factory.Sequence(lambda n: f"user{n}@example.com")
        password = factory.django.Password("correct-horse-battery")

    return UserFactory
