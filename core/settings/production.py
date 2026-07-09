from .common import *
import os
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured


load_dotenv(os.path.join(BASE_DIR, '.env'))

def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return value

def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

def _env_csv(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]

SECRET_KEY = _require_env("DJANGO_SECRET_KEY")

DEBUG = False

ALLOWED_HOSTS = _env_csv("ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Missing required environment variable: ALLOWED_HOSTS")
if "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must not contain '*' in production")

CSRF_TRUSTED_ORIGINS = _env_csv("CSRF_TRUSTED_ORIGINS")

CORS_ALLOWED_ORIGINS = _env_csv("CORS_ALLOWED_ORIGINS")
member_portal_origin = os.getenv("MEMBER_PORTAL_ORIGIN", "").strip()
if member_portal_origin and member_portal_origin not in CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS.append(member_portal_origin)
CORS_ALLOW_CREDENTIALS = _env_bool("CORS_ALLOW_CREDENTIALS", False)

db_engine = os.getenv("DB_ENGINE", "django.db.backends.mysql").strip()
if db_engine == "django.db.backends.sqlite3":
    raise ImproperlyConfigured("SQLite is not allowed for production. Configure MySQL DB_* environment variables.")
if db_engine == "django.db.backends.mysql":
    try:
        import pymysql
    except ImportError as exc:
        raise ImproperlyConfigured("PyMySQL is required for the production MySQL backend.") from exc
    pymysql.install_as_MySQLdb()

DATABASES = {
    'default': {
        'ENGINE': db_engine,
        'NAME': _require_env('DB_NAME'),
        'USER': _require_env('DB_USER'),
        'PASSWORD': _require_env('DB_PASSWORD'),
        'HOST': _require_env('DB_HOST'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'CONN_MAX_AGE': int(os.getenv("DB_CONN_MAX_AGE", "60")),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}


# Security Hardening
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", False)
SECURE_REFERRER_POLICY = os.getenv("SECURE_REFERRER_POLICY", "same-origin")
X_FRAME_OPTIONS = os.getenv("X_FRAME_OPTIONS", "DENY")

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = _env_bool("SECURE_HSTS_PRELOAD", False)

if _env_bool("SECURE_PROXY_SSL_HEADER_ENABLED", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
