from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _create_cache_table(sender, using, **kwargs):
    # DatabaseCache needs its table; createcachetable is idempotent and routes itself.
    from django.core.management import call_command

    call_command("createcachetable", database=using, verbosity=0)


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        post_migrate.connect(_create_cache_table, sender=self, dispatch_uid="accounts_create_cache_table")
