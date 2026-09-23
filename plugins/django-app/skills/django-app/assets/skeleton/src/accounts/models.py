from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models import Func


class UUIDv7(Func):
    """PostgreSQL 18+ uuidv7() — time-ordered UUID primary keys.

    With db_default, `self.pk` is a truthy sentinel until saved: test newness
    with `self._state.adding`, never `if self.pk`.
    """

    function = "uuidv7"
    output_field = models.UUIDField()


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, db_default=UUIDv7(), editable=False)
    username = None
    email = models.EmailField(unique=True)
    # [tenant]
    # One user, one tenant. RLS context for every request comes from this FK.
    tenant = models.ForeignKey("tenants.Tenant", on_delete=models.PROTECT, null=True, blank=True, related_name="users")

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"
        READER = "reader", "Reader"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)
    # [/tenant]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email
