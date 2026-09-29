"""Settings for the in-browser demo: Orbit runs in the visitor's browser (Pyodide) with SQLite.

Never use in production.
"""
import os

from config.settings import *  # noqa: F401,F403

DATA_DIR = os.environ.get("ORBIT_DEMO_DATA", "/data")
DEBUG = False
ALLOWED_HOSTS = ["*"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.path.join(DATA_DIR, "db.sqlite3")}}
MEDIA_ROOT = os.path.join(DATA_DIR, "media")
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
ORBIT_BASE_URL = "https://orbit.demo"
ORBIT_DEMO = True
# Hashing a password 1,000,000 times is slow in the browser; the demo has no real secrets.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = []
SECRET_KEY = "orbit-demo-not-secret"
MIDDLEWARE = MIDDLEWARE + ["demo.middleware.DemoPageMiddleware"]  # noqa: F405
TEMPLATES[0]["OPTIONS"]["context_processors"].append("demo.middleware.demo_context")  # noqa: F405
