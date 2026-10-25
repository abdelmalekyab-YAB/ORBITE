"""Réglages Django d'Orbit. Voir CLAUDE.md et docs/."""
import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"] if DEBUG else os.environ.get("ALLOWED_HOSTS", "").split(",")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "rest_framework_simplejwt", "corsheaders", "django_filters",
    "apps.accounts", "apps.projects", "apps.tickets", "apps.finance", "apps.notifications", "apps.billing",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
ROOT_URLCONF = "orbit.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
              "OPTIONS": {"context_processors": ["django.template.context_processors.request",
                                                 "django.contrib.auth.context_processors.auth",
                                                 "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "orbit.wsgi.application"
DATABASES = {"default": dj_database_url.config(default=os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR}/db.sqlite3"))}

AUTH_USER_MODEL = "accounts.User"
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 50,
    "EXCEPTION_HANDLER": "orbit.exceptions.api_exception_handler",
}
# Pièces jointes : S3-compatible dès que le bucket est configuré, disque local sinon (dev / tests).
if os.environ.get("AWS_STORAGE_BUCKET_NAME"):
    STORAGES = {"default": {"BACKEND": "storages.backends.s3.S3Storage"},
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
    AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL") or None
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME") or None
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True  # URLs signées : un fichier n'est jamais public
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
SIMPLE_JWT = {"ACCESS_TOKEN_LIFETIME": timedelta(hours=8), "REFRESH_TOKEN_LIFETIME": timedelta(days=30)}
CORS_ALLOWED_ORIGINS = [os.environ.get("FRONTEND_URL", "http://localhost:5173")]

CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_TASK_ALWAYS_EAGER = os.environ.get("CELERY_EAGER", "0") == "1"
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    "rappel-client": {"task": "apps.notifications.tasks.remind_waiting_clients",
                      "schedule": crontab(hour=9, minute=0)},
    "digest-quotidien": {"task": "apps.notifications.tasks.daily_digest", "schedule": crontab(hour=8, minute=0)},
}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_RESET_TIMEOUT = 7 * 24 * 3600  # liens d'invitation et de réinitialisation : 7 jours
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "0") == "1"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Orbit <orbit@digitalia-ltd.com>")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}

if not DEBUG:
    # Production derrière le reverse proxy (Caddy) qui termine le HTTPS.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    CSRF_TRUSTED_ORIGINS = [FRONTEND_URL]
    if SECRET_KEY == "dev-only-insecure":
        raise RuntimeError("DJANGO_SECRET_KEY doit être défini en production.")

if os.environ.get("SENTRY_DSN"):  # supervision des erreurs (optionnelle)
    import sentry_sdk

    sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], traces_sample_rate=0.1, send_default_pii=False)

# Facturation : Zoho Books en LECTURE SEULE (aucune écriture possible, voir apps/billing/services/zoho.py).
ZOHO_BOOKS = {
    "ORGANIZATION_ID": os.environ.get("ZOHO_ORGANIZATION_ID", ""),
    "API_BASE": os.environ.get("ZOHO_API_BASE", "https://www.zohoapis.com/books/v3"),
    "ACCOUNTS_BASE": os.environ.get("ZOHO_ACCOUNTS_BASE", "https://accounts.zoho.com"),
    "CLIENT_ID": os.environ.get("ZOHO_CLIENT_ID", ""),
    "CLIENT_SECRET": os.environ.get("ZOHO_CLIENT_SECRET", ""),
    "REFRESH_TOKEN": os.environ.get("ZOHO_REFRESH_TOKEN", ""),
}
