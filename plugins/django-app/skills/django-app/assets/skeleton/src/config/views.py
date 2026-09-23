import logging

from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)


def health_check(request):
    """200 if the database answers, 503 if not. Used by Docker, Traefik and deploy verification."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        # Log, don't return: psycopg errors carry host and role names.
        logger.exception("health check failed")
        return HttpResponse("unhealthy", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")


def server_error(request):
    """500 page with the Sentry event id, so the page can offer the feedback widget."""
    try:
        from sentry_sdk import last_event_id

        event_id = last_event_id()
    except ImportError:
        event_id = None
    return render(request, "errors/500.html", {"sentry_event_id": event_id}, status=500)
