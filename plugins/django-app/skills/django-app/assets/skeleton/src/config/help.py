# [help]
from django.conf import settings
from django.http import Http404
from django.views.static import serve


def help_docs(request, path=""):
    """Serve the built Zensical site (help_site/) at /help/, mapping directories to index.html."""
    root = settings.BASE_DIR / "help_site"
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()):
        raise Http404
    if target.is_dir():
        path = f"{path.rstrip('/')}/index.html".lstrip("/")
    return serve(request, path, document_root=root)
# [/help]
