from .common import *

DEBUG = True
ALLOWED_HOSTS = []

# SQLite is fine for dev (already in common)
# You can add dev-only tools here:
# INSTALLED_APPS += [
#     "debug_toolbar",
# ]

# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.sqlite3",
#         "NAME": str(BASE_DIR / "db.sqlite3"),
#     }
# }

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'codemsdx_campusnexus_db',
        'USER': 'codemsdx_nexus_admin',
        'PASSWORD': 'H3artB3at!',
        'HOST': 'localhost',  # or your remote DB host if hosted elsewhere
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}


MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

INTERNAL_IPS = ["127.0.0.1"]
