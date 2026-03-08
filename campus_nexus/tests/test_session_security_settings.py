from django.conf import settings
from django.test import SimpleTestCase


class SessionSecuritySettingsTests(SimpleTestCase):
    def test_admin_session_expiry_defaults_are_hardened(self):
        self.assertLessEqual(settings.SESSION_COOKIE_AGE, 1800)
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
