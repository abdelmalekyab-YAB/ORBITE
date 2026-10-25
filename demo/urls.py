from django.conf import settings
from django.urls import include, re_path
from django.views.static import serve

urlpatterns = [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    re_path(r"", include("orbit.urls")),
]
