from .common import *
import os

DEBUG = False

ALLOWED_HOSTS = ["yourdomain.com", "www.yourdomain.com", "localhost"]

# Use environment variable for secret key
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")

# Use PostgreSQL or your production DB here
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Security Hardening
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
