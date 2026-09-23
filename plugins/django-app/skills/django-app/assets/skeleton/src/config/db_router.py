# [tenant]
"""Route between the two DB roles.

`default` = myapp_app (RLS applies) for tenant-scoped web traffic.
`admin`   = myapp_admin (BYPASSRLS, owns the tables) for migrations, platform-wide
            tables, the Django admin and cross-tenant jobs.
"""

import threading

# Set by TenantRLSMiddleware for staff on /admin/ only. Without it the admin runs
# RLS-scoped to the staff user's own tenant: changelists show one tenant, and
# deleting a tenant fails at COMMIT because the cascade can't see its children.
_ADMIN_REQUEST = threading.local()
# Aliases mid-migrate: RunPython data migrations (ours and third-party) call
# Model.objects without .using(), so pin all ORM access to admin while they run.
_MIGRATING: set = set()


def enter_admin_request():
    _ADMIN_REQUEST.active = True


def exit_admin_request():
    _ADMIN_REQUEST.active = False


def enter_migration(using=None, **kwargs):
    _MIGRATING.add(using)


def exit_migration(using=None, **kwargs):
    _MIGRATING.discard(using)


class RLSRouter:
    # Platform-wide tables, or tables read before a tenant context exists.
    ADMIN_APPS = frozenset({"admin", "contenttypes", "sessions", "sites", "auth", "procrastinate"})

    def _target(self, model):
        if _MIGRATING or getattr(_ADMIN_REQUEST, "active", False):
            return "admin"
        if model._meta.app_label in self.ADMIN_APPS:
            return "admin"
        # Tenant and User stay on default (no RLS on them): moving them to admin creates
        # cross-alias FKs that break test teardown.
        return None

    def db_for_read(self, model, **hints):
        return self._target(model)

    def db_for_write(self, model, **hints):
        return self._target(model)

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == "admin"  # the app role never changes schema
# [/tenant]
