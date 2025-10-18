from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key")

INSTALLED_APPS = [
    "campus_nexus",
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
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "campus_nexus.middleware.AssociationWhiteLabellingMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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
        "NAME": BASE_DIR / "db.sqlite3",
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
    # CSS classes that are applied to the logo above
    "site_logo_classes": "img-circle",
    # Relative path to a favicon for your site
    "site_icon": "images/favicon.ico",
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
        {"name": "Log out", "url": "admin:logout", "icon": "fas fa-sign-out-alt"},
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
        "campus_nexus.associationadmins",
        "campus_nexus.associations",
        "campus_nexus.cabinet_members",
        "campus_nexus.cabinets",
        "campus_nexus.courses",
        "campus_nexus.events",
        "campus_nexus.faculties",
        "campus_nexus.fees",
        "campus_nexus.members",
        "campus_nexus.memberships",
        "campus_nexus.payments",
        "campus_nexus.feedbacks",
    ],
    # Custom icons for side menu apps/models
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "campus_nexus.associationadmin": "fas fa-user-shield",
        "campus_nexus.association": "fas fa-university",
        "campus_nexus.cabinetmember": "fas fa-user-tie",
        "campus_nexus.cabinet": "fas fa-briefcase",
        "campus_nexus.course": "fas fa-book",
        "campus_nexus.event": "fas fa-calendar-alt",
        "campus_nexus.faculty": "fas fa-chalkboard-teacher",
        "campus_nexus.fee": "fas fa-dollar-sign",
        "campus_nexus.member": "fas fa-user-friends",
        "campus_nexus.membership": "fas fa-id-card",
        "campus_nexus.payment": "fas fa-credit-card",
        "campus_nexus.feedback": "fas fa-comment-dots",
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
    "navbar_small_text": False,
    "footer_small_text": False,
    "navbar_fixed": True,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
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
