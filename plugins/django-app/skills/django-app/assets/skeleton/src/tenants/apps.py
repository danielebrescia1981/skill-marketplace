# [tenant]
from django.apps import AppConfig


class TenantsConfig(AppConfig):
    name = "tenants"

    def ready(self):
        from django.db.backends.signals import connection_created
        from django.db.models.signals import post_migrate, pre_migrate

        from config.db_router import enter_migration, exit_migration
        from tenants import checks  # noqa: F401  (registers system checks)
        from tenants.rls import reset_rls_on_new_connection

        pre_migrate.connect(enter_migration, dispatch_uid="rls_router_enter_migration")
        post_migrate.connect(exit_migration, dispatch_uid="rls_router_exit_migration")
        # django-rls's own receivers are switched off in settings.DJANGO_RLS.
        connection_created.connect(reset_rls_on_new_connection, dispatch_uid="myapp_reset_rls_on_connect")
# [/tenant]
