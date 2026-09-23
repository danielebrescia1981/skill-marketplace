# [tenant]
from django.contrib import admin

from tenants.models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ["slug", "name", "is_active", "created_at"]
    search_fields = ["slug", "name"]
# [/tenant]
