from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    ENABLE_ADMIN_LOGIN_RATE_LIMIT=True,
    ADMIN_LOGIN_MAX_ATTEMPTS=2,
    ADMIN_LOGIN_LOCKOUT_SECONDS=60,
)
class AdminLoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="staffuser",
            email="staff@example.com",
            password="pass12345",
            is_staff=True,
        )

    def test_admin_login_is_locked_after_repeated_failures(self):
        login_url = reverse("admin:login")
        payload = {"username": self.user.username, "password": "wrong-pass"}

        self.assertEqual(self.client.post(login_url, payload).status_code, 200)
        second = self.client.post(login_url, payload)
        self.assertEqual(second.status_code, 302)
        self.assertIn("locked=1", second.url)
        self.assertIn("lockout_until=", second.url)

        third = self.client.post(login_url, payload)
        self.assertEqual(third.status_code, 302)
        self.assertIn("locked=1", third.url)

    def test_successful_login_resets_failed_attempt_counter(self):
        login_url = reverse("admin:login")

        self.assertEqual(
            self.client.post(login_url, {"username": self.user.username, "password": "wrong-pass"}).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(login_url, {"username": self.user.username, "password": "pass12345"}).status_code,
            302,
        )

        self.client.logout()
        self.assertEqual(
            self.client.post(login_url, {"username": self.user.username, "password": "wrong-pass"}).status_code,
            200,
        )
