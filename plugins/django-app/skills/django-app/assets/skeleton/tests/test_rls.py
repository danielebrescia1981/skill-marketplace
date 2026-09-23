# [tenant]
"""Tenant isolation guards. These assert over every model, so the next app to forget is caught too."""

from django.apps import apps
from django.core.checks import run_checks
from django.db import connections
import pytest

# Tables with a tenant column that are read before any tenant context exists (login).
RLS_EXEMPT_TABLES = {"accounts_user"}


@pytest.mark.django_db
def test_every_table_with_a_tenant_column_has_an_rls_policy():
    """Inheriting TenantIsolatedModel declares a policy; only the migration creates it.

    Historical* tables (simple-history) copy the tenant FK and are the easy miss.
    """
    tables = sorted(
        m._meta.db_table
        for m in apps.get_models()
        if m._meta.managed and any(f.name == "tenant" for f in m._meta.fields)
    )
    with connections["admin"].cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, c.relrowsecurity, count(p.polname) FROM pg_class c "
            "LEFT JOIN pg_policy p ON p.polrelid = c.oid WHERE c.relname = ANY(%s) "
            "GROUP BY c.relname, c.relrowsecurity",
            [tables],
        )
        state = {name: enabled and policies > 0 for name, enabled, policies in cursor.fetchall()}
    unprotected = [t for t in tables if t not in RLS_EXEMPT_TABLES and not state.get(t)]
    assert not unprotected, f"tenant tables without RLS + a policy: {unprotected}"


@pytest.mark.django_db
def test_app_role_cannot_bypass_rls():
    errors = [e for e in run_checks(databases=["default"], include_deployment_checks=True) if e.id == "tenants.E001"]
    assert not errors, errors
# [/tenant]
