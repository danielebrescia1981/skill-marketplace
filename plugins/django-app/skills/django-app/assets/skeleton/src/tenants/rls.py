# [tenant]
"""RLS context: which tenant the current transaction may see.

`rls.tenant_id` is set transaction-locally (set_config(..., true)), so it can
never leak to the next request on a pooled connection.
"""

from contextlib import contextmanager
import threading

from django.db import connection

_local = threading.local()


def get_current_tenant_id() -> str | None:
    return getattr(_local, "tenant_id", None)


def set_rls_tenant(tenant_id: str) -> None:
    """Pin the tenant for the current transaction. Must run inside transaction.atomic()."""
    _local.tenant_id = tenant_id
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('rls.tenant_id', %s, true)", [tenant_id])


def clear_rls_tenant() -> None:
    """Clear the tenant. Note: inside a transaction the setting becomes '' (not NULL); the policy matches nothing."""
    _local.tenant_id = None
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('rls.tenant_id', '', true)")


@contextmanager
def tenant_context(tenant_id: str | None):
    """Scope ORM access to one tenant — for tasks, commands and tests. Reentrant.

    with transaction.atomic(), tenant_context(slug):
        Document.objects.all()   # only this tenant's rows
    """
    previous = get_current_tenant_id()
    set_rls_tenant(tenant_id) if tenant_id else clear_rls_tenant()
    try:
        yield
    finally:
        set_rls_tenant(previous) if previous else clear_rls_tenant()


def reset_rls_on_new_connection(sender, connection, **kwargs) -> None:
    """connection_created receiver: clear stale context on *this* connection.

    Replaces django-rls's receiver, which resets django.db.connection (the app
    alias) whichever connection was created — so the first admin-alias query in
    a tenant transaction wiped the app connection's tenant.
    """
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('rls.tenant_id', '', false)")
# [/tenant]
