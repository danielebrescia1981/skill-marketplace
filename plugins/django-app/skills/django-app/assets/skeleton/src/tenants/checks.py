# [tenant]
from django.core.checks import Error, register
from django.db import connections


@register("database", deploy=True)
def app_role_cannot_bypass_rls(app_configs=None, databases=None, **kwargs):
    """If the app role is a superuser or has BYPASSRLS, every policy is silently inert.

    That is exactly how tenant data leaked in appsfolio (PLAN_RLS_SECURITY.md).
    Runs under `manage.py check --deploy --database default`.
    """
    if not databases or "default" not in databases:
        return []
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        superuser, bypass = cursor.fetchone()
    if superuser or bypass:
        return [Error("The default DB role can bypass row-level security; tenant isolation is off.", id="tenants.E001")]
    return []
# [/tenant]
