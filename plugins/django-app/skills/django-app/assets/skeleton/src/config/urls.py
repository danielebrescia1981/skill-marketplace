from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView

from config import views
# [help]
from config.help import help_docs
# [/help]

urlpatterns = [
    path("ht/", views.health_check, name="health_check"),
    path(
        ".well-known/change-password",
        RedirectView.as_view(pattern_name="account_change_password", permanent=False),
    ),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    # [help]
    path("help/", help_docs, name="help"),
    path("help/<path:path>", help_docs),
    # [/help]
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
]

if "django_browser_reload" in settings.INSTALLED_APPS:
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]

handler500 = "config.views.server_error"
