from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or reset a superuser (idempotent), including the verified allauth EmailAddress it needs to log in."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("--password", help="default: prompt")

    def handle(self, *args, email, password, **opts):
        if not password:
            from getpass import getpass

            password = getpass(f"Password for {email}: ")
        User = get_user_model()
        user, created = User.objects.get_or_create(email=email, defaults={"is_staff": True, "is_superuser": True})
        user.is_staff = user.is_superuser = user.is_active = True
        user.set_password(password)
        user.save()
        # Without a verified EmailAddress, mandatory verification locks the superuser out.
        EmailAddress.objects.update_or_create(user=user, email=email, defaults={"verified": True, "primary": True})
        self.stderr.write(f"{'Created' if created else 'Updated'} superuser {email}")
