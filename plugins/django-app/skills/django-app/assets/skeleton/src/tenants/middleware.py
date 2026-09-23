# [tenant]
"""Resolve the tenant and pin the RLS context for the request.

The subdomain is cosmetic (canonical URLs, branding) and never grants access:
the RLS context comes from the authenticated user's own tenant.
"""

import logging

from django.conf import settings
from django.db import InterfaceError, OperationalError, transaction
from django.http import HttpResponse, HttpResponseRedirect

from config.db_router import enter_admin_request, exit_admin_request
from tenants.rls import set_rls_tenant

logger = logging.getLogger(__name__)

# An entry ending in "/" is a prefix; anything else must match exactly, so "/mcp"
# can't silently exempt "/mcpanything".
TENANT_EXEMPT_PATHS = ["/", "/admin/", "/accounts/", "/static/", "/media/", "/ht/", "/help/", "/.well-known/"]


def is_exempt(path: str) -> bool:
    return any(path.startswith(e) if e.endswith("/") and e != "/" else path == e for e in TENANT_EXEMPT_PATHS)


def subdomain_for(request) -> str | None:
    host = request.get_host().split(":")[0]
    for base in settings.TENANT_BASE_DOMAINS:
        if host.endswith(f".{base}"):
            return host[: -(len(base) + 1)]
    return None


class TenantRLSMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        tenant = getattr(user, "tenant", None) if user and user.is_authenticated else None
        request.tenant = tenant

        # Canonicalise page loads to the user's own subdomain. HTMX requests are
        # served in place (a redirect would swap a whole page into a fragment target).
        sub = subdomain_for(request)
        if tenant and sub != tenant.slug and not is_exempt(request.path) and not request.headers.get("HX-Request"):
            host = request.get_host()
            base = next((b for b in settings.TENANT_BASE_DOMAINS if host.split(":")[0].endswith(b)), None)
            if base:
                port = f":{host.split(':')[1]}" if ":" in host else ""
                scheme = "https" if request.is_secure() else "http"
                return HttpResponseRedirect(f"{scheme}://{tenant.slug}.{base}{port}{request.get_full_path()}")

        # The Django admin is cross-tenant by design: staff requests there run on the
        # BYPASSRLS admin alias (config.db_router).
        admin_request = request.path.startswith("/admin/") and getattr(user, "is_staff", False)
        if admin_request:
            enter_admin_request()
        try:
            with transaction.atomic():
                if tenant:
                    set_rls_tenant(tenant.slug)
                response = self.get_response(request)
                if response.status_code >= 500:
                    # Inner middleware already turned the exception into a response; don't commit.
                    transaction.set_rollback(True)
        except OperationalError, InterfaceError:
            logger.exception("database unavailable")
            return HttpResponse("Service temporarily unavailable", status=503)
        finally:
            # Thread-local: must be released or the next request on this thread inherits BYPASSRLS.
            if admin_request:
                exit_admin_request()
        return response
# [/tenant]
