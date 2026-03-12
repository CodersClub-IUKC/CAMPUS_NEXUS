import re
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from campus_nexus.models import Association, AssociationAdmin
from campus_nexus.services.onboarding import send_onboarding_invitation_email


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class OnboardingInvitationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="invite.user",
            email="invite.user@example.com",
            password="StrongPass123!",
            is_staff=True,
        )

    def test_send_onboarding_email_contains_valid_password_setup_link(self):
        sent = send_onboarding_invitation_email(
            user=self.user,
            invited_by="System Admin",
            base_url="http://testserver",
        )
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(r"https?://testserver(?P<path>/reset/[^\s]+)", mail.outbox[0].body)
        self.assertIsNotNone(match)

        response = self.client.get(match.group("path"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Set a new password")

    def test_send_onboarding_email_skips_when_user_has_no_email(self):
        self.user.email = ""
        self.user.save(update_fields=["email"])

        sent = send_onboarding_invitation_email(user=self.user, invited_by="System Admin")
        self.assertFalse(sent)
        self.assertEqual(len(mail.outbox), 0)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class CreateAssociationAdminCommandTests(TestCase):
    def setUp(self):
        self.association = Association.objects.create(name="Coders Club")

    def test_command_creates_admin_and_sends_invitation(self):
        stdout = StringIO()
        with patch(
            "builtins.input",
            side_effect=[
                "association.admin",
                "association.admin@example.com",
                "Association",
                "Admin",
                str(self.association.id),
            ],
        ):
            call_command("create_association_admin", stdout=stdout)

        user_model = get_user_model()
        user = user_model.objects.get(username="association.admin")

        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(
            AssociationAdmin.objects.filter(user=user, association=self.association).exists()
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/reset/", mail.outbox[0].body)

    def test_command_manual_password_mode_skips_invitation(self):
        stdout = StringIO()
        with patch(
            "builtins.input",
            side_effect=[
                "manual.password.admin",
                "manual.password.admin@example.com",
                "Manual",
                "Admin",
                str(self.association.id),
                "ManualPass123!",
            ],
        ):
            call_command("create_association_admin", manual_password=True, stdout=stdout)

        user_model = get_user_model()
        user = user_model.objects.get(username="manual.password.admin")
        self.assertTrue(user.has_usable_password())
        self.assertEqual(len(mail.outbox), 0)
