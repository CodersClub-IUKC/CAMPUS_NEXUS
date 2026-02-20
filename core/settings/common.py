from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key")

INSTALLED_APPS = [
    "campus_nexus.apps.CampusNexusConfig",
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_extensions",
    "rest_framework",
    "rest_framework_simplejwt",
    # debug_toolbar is added only in development.py
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Must be right after SecurityMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # "campus_nexus.middleware.AssociationWhiteLabellingMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "static")

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}



# Jazzmin Settings
JAZZMIN_SETTINGS = {
    # Title of the window
    "site_title": "Campus Nexus Admin",
    # Title on the login screen (19 chars max)
    "site_header": "Campus Nexus",
    # Title on the brand (19 chars max)
    "site_brand": "Campus Nexus",
    "site_logo": "img/CAMPUS_NEXUS.png",
    # Logo to use for login form
    "login_logo": "img/CAMPUS_NEXUS.png",
    "custom_css": "css/admin_custom.css",
    # CSS classes that are applied to the logo above
    "site_logo_classes": "img-circle",
    # Relative path to a favicon for your site
    "site_icon": "images/CAMPUS_NEXUS.png",
    # Welcome text on the login screen
    "welcome_sign": "Welcome to Campus Nexus Administration",
    # Copyright on the footer
    "copyright": "Coder's Club IUIU-KC",
    "user_avatar": None,
    # Links to put along the top menu
    "topmenu_links": [
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        {},
        {"model": "auth.User"},
        {"app": "campus_nexus"},
        {"name": "Submit Feedback", "url": "admin:submit_feedback", "icon": "fas fa-bug"},

    ],
    # Additional links to include in the user menu on the top right
    "usermenu_links": [
        {},
        {"model": "auth.user"},
        {
            "name": "Profile",
            "url": "admin:auth_user_change",  # Links to current user change form
            "icon": "fas fa-user",
        },
        {"name": "Submit Feedback", "url": "admin:submit_feedback", "icon": "fas fa-bug"},

    ],
    #############
    # Side Menu #
    #############
    # Whether to display the side menu
    "show_sidebar": True,
    # Whether to aut-expand the menu
    "navigation_expanded": True,
    # Hide these apps when generating side menu
    "hide_apps": [],
    # Hide these models when generating side menu
    "hide_models": [],
    # List of apps (and models) to base side menu ordering off of

    "order_with_respect_to": [
        "auth",
        "campus_nexus",
        "campus_nexus.associationadmin",
        "campus_nexus.association",
        "campus_nexus.cabinet_member",
        "campus_nexus.cabinet",
        "campus_nexus.course",
        "campus_nexus.event",
        "campus_nexus.faculty",
        "campus_nexus.fee",
        "campus_nexus.guildcabinet",
        "campus_nexus.guildexecutive",
        "campus_nexus.announcement",
        "campus_nexus.member",
        "campus_nexus.membership",
        "campus_nexus.payment",
        "campus_nexus.feedback",
        "campus_nexus.guild",
        "campus_nexus.dean",
        "campus_nexus.charge"
    ],
    # Custom icons for side menu apps/models
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.group": "fas fa-users",
        "campus_nexus.associationadmin": "fas fa-user-shield",
        "campus_nexus.association": "fas fa-university",
        "campus_nexus.cabinetmember": "fas fa-user-tie",
        "campus_nexus.cabinet": "fas fa-briefcase",
        "campus_nexus.course": "fas fa-book",
        "campus_nexus.event": "fas fa-calendar-alt",
        "campus_nexus.faculty": "fas fa-chalkboard-teacher",
        "campus_nexus.fee": "fas fa-dollar-sign",
        "campus_nexus.guildcabinet": "fas fa-users-cog",
        "campus_nexus.announcement": "fas fa-bullhorn",
        "campus_nexus.member": "fas fa-user-friends",
        "campus_nexus.payment": "fas fa-credit-card",
        "campus_nexus.feedback": "fas fa-comment-dots",
        "campus_nexus.guild": "fas fa-users",
        "campus_nexus.charge": "fas fa-file-invoice-dollar",
        "campus_nexus.dean": "fas fa-user-tie",
        "campus_nexus.guildexecutive": "fas fa-users-cog",
        "campus_nexus.membership": "fas fa-id-card",
    },
    # Icons that are used when one is not manually specified
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": False,
    "custom_js": "js/custom_jazzmin.js",
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
    # Add a language dropdown into the admin
    "language_chooser": False,
}

# UI Tweaks for colors and theme
JAZZMIN_UI_TWEAKS = {
    "theme": "flatly",
    "navbar_small_text": False,
    "footer_small_text": False,
    "navbar_fixed": True,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": True,
    "body_small_text": False,
    "footer_small_text": True,
    "navbar_small_text": False,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
    "actions_sticky_top": False,
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

ASSOCIATION_DEFAULT_THEME = ("#3b82f6", "#64748b")

# ---------------------------------------------------------------------
# Email (SMTP - env driven)

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "false").lower() == "true"

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Campus Nexus <no-reply@campusnexus.local>")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
