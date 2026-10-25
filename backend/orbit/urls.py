import redis
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import LoginView


def health(_request):
    """Supervision : vérifie la base et le broker ; 503 si l'un des deux est indisponible."""
    checks = {}
    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        checks["database"] = "down"
    try:
        redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=1).ping()
        checks["broker"] = "ok"
    except Exception:  # noqa: BLE001
        checks["broker"] = "down"
    ok = all(v == "ok" for v in checks.values())
    return JsonResponse({"status": "ok" if ok else "degraded", "app": "orbit", **checks}, status=200 if ok else 503)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health", health),
    path("api/v1/auth/login", LoginView.as_view()),
    path("api/v1/auth/refresh", TokenRefreshView.as_view()),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.projects.urls")),
    path("api/v1/", include("apps.tickets.urls")),
    path("api/v1/", include("apps.finance.urls")),
    path("api/v1/", include("apps.notifications.urls")),
]
if settings.DEBUG:  # en production, les fichiers sont servis par S3
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
