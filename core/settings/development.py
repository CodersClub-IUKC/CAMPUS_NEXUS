from .common import *

DEBUG = True
ALLOWED_HOSTS = []

# SQLite is fine for dev (already in common)
# You can add dev-only tools here:
INSTALLED_APPS += [
    "debug_toolbar",
]

MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

INTERNAL_IPS = ["127.0.0.1"]
