import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AdminPasswordResetFlowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="staff.reset",
            email="staff.reset@example.com",
            password="StrongPass123!",
            is_staff=True,
        )
        self.non_staff_user = user_model.objects.create_user(
            username="student.reset",
            email="student.reset@example.com",
            password="StrongPass123!",
            is_staff=False,
        )

    def test_admin_login_shows_password_reset_link(self):
        response = self.client.get(reverse("admin:login"))
        self.assertContains(response, reverse("admin_password_reset"))

    def test_staff_user_receives_reset_email_and_can_open_link(self):
        response = self.client.post(
            reverse("admin_password_reset"),
            {"email": self.staff_user.email},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

        email_body = mail.outbox[0].body
        match = re.search(r"https?://testserver(?P<path>/reset/[^\s]+)", email_body)
        self.assertIsNotNone(match)

        confirm_response = self.client.get(match.group("path"), follow=True)
        self.assertEqual(confirm_response.status_code, 200)
        self.assertContains(confirm_response, "Set a new password")

    def test_non_staff_user_does_not_receive_reset_email(self):
        response = self.client.post(
            reverse("admin_password_reset"),
            {"email": self.non_staff_user.email},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)
