"""Django settings for the in-browser demo (Pyodide). Never used in production."""
import os

from orbit.settings import *  # noqa: F401,F403

DATA_DIR = os.environ.get("ORBIT_DEMO_DATA", "/data")
DEBUG = False
ALLOWED_HOSTS = ["*"]
SECRET_KEY = "orbit-demo-only-not-a-secret-0123456789abcdefghijklmnop"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.path.join(DATA_DIR, "db.sqlite3")}}
MEDIA_ROOT = os.path.join(DATA_DIR, "media")
ROOT_URLCONF = "demo.urls"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_BROKER_URL = "memory://"
FRONTEND_URL = os.environ.get("ORBIT_DEMO_URL", "https://abdelmalekyab-yab.github.io/ORBITE")
# Hashing a password 1,000,000 times is slow in the browser; the demo has no real secrets.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
LOGGING = {"version": 1, "disable_existing_loggers": True}
