from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "admin-login-rate-limit-tests",
    }
}


@override_settings(
    ENABLE_ADMIN_LOGIN_RATE_LIMIT=True,
    ADMIN_LOGIN_MAX_ATTEMPTS=5,
    ADMIN_LOGIN_LOCKOUT_SECONDS=30,
    CACHES=TEST_CACHES,
)
class AdminLoginRateLimitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="locked_user",
            email="locked@example.com",
            password="correct-password",
            is_staff=True,
        )

    def test_lockout_triggers_on_5th_failed_attempt(self):
        login_url = reverse("admin:login")
        payload = {
            "username": self.user.username,
            "password": "wrong-password",
        }

        for _ in range(4):
            response = self.client.post(login_url, payload, follow=False)
            self.assertEqual(response.status_code, 200)

        locked_response = self.client.post(login_url, payload, follow=False)
        self.assertEqual(locked_response.status_code, 302)

        location = locked_response["Location"]
        self.assertIn("locked=1", location)
        self.assertIn("lockout_until=", location)
        self.assertIn("username=locked_user", location)

        lockout_page = self.client.get(location)
        self.assertEqual(lockout_page.status_code, 200)
        self.assertContains(lockout_page, "lockout-countdown")
