"""
Passenger WSGI entry point for the Namecheap/cPanel Python application.

The cPanel app should point at this file. It intentionally does not run
migrations, collectstatic, git commands, or any deployment work at import time.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.production")

from core.wsgi import application  # noqa: E402,F401
