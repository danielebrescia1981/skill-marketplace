# [tenant]
from django.core.validators import RegexValidator
from django.db import models
from django_rls.models import RLSModel
from django_rls.policies import BasePolicy

subdomain_validator = RegexValidator(
    r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", "Lowercase letters, digits and hyphens; must be a valid DNS label."
)


class Tenant(models.Model):
    """A customer organisation. The slug PK doubles as the subdomain and keeps the policy a text compare.

    No RLS on this table: it is read before any tenant context exists (login, subdomain lookup).
    """

    slug = models.SlugField(primary_key=True, max_length=63, validators=[subdomain_validator])
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class SlugTenantPolicy(BasePolicy):
    """tenant_id = current_setting('rls.tenant_id').

    No empty-context bypass: with no tenant set, no rows match (fail closed).
    Cross-tenant access is the admin role's job (BYPASSRLS), not the policy's.
    """

    def __init__(self, name: str, tenant_field: str = "tenant", **kwargs):
        self.tenant_field = tenant_field
        super().__init__(name, **kwargs)

    def validate(self) -> None:
        super().validate()
        self.validate_field_name(self.tenant_field)

    def get_sql_expression(self) -> str:
        return f"{self.tenant_field}_id = current_setting('rls.tenant_id', true)"


class TenantIsolatedModel(RLSModel):
    """Base for every tenant-scoped model.

    Inheriting this DECLARES the policy; it does not CREATE it. Each app ships a
    `NNNN_rls_enable` migration with EnableRLS + CreatePolicy for its models
    (Historical* tables included). tests/test_rls.py fails if one is missing.
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="%(class)s_items", db_index=True)

    class Meta:
        abstract = True
        rls_policies = [SlugTenantPolicy("tenant_isolation", tenant_field="tenant")]

    def save(self, *args, **kwargs):
        if not self.tenant_id:
            raise ValueError(f"{type(self).__name__} saved without a tenant")
        super().save(*args, **kwargs)
# [/tenant]
