from .common import *

import os

DEBUG = True
ALLOWED_HOSTS = []

from dotenv import load_dotenv
load_dotenv()

# Add dev-only tools (guarded to avoid duplicate app labels)
if "debug_toolbar" not in INSTALLED_APPS:
    INSTALLED_APPS += [
        "debug_toolbar",
    ]

# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": str(BASE_DIR / "db.sqlite3"),
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(BASE_DIR / 'db.sqlite3'),
    }
}

if "debug_toolbar.middleware.DebugToolbarMiddleware" not in MIDDLEWARE:
    MIDDLEWARE += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ]

INTERNAL_IPS = ["127.0.0.1"]


EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    f"Campus Nexus <{EMAIL_HOST_USER}>"
)
