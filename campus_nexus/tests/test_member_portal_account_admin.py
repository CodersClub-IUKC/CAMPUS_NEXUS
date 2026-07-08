from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from campus_nexus.models import Association, AssociationAdmin, AuditLog, Dean, Guild, Member


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class MemberPortalAccountAdminTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            username="root",
            email="root@example.com",
            password="StrongPass123!",
        )
        self.guild_user = user_model.objects.create_user(
            username="guild",
            email="guild@example.com",
            password="StrongPass123!",
            is_staff=True,
        )
        Guild.objects.create(user=self.guild_user)
        self.dean_user = user_model.objects.create_user(
            username="dean.portal",
            email="dean.portal@example.com",
            password="StrongPass123!",
            is_staff=True,
        )
        Dean.objects.create(user=self.dean_user)
        self.association = Association.objects.create(name="Coders Club")
        self.assoc_user = user_model.objects.create_user(
            username="assoc.portal",
            email="assoc.portal@example.com",
            password="StrongPass123!",
            is_staff=True,
        )
        AssociationAdmin.objects.create(user=self.assoc_user, association=self.association)
        self.member = Member.objects.create(
            first_name="Ssali",
            last_name="Jamil",
            email="ssalijamal697@gmail.com",
            phone="+256700000010",
            registration_number="223-063012-27433",
            member_type="student",
        )

    def change_url(self, member=None):
        return reverse("admin:campus_nexus_member_change", args=[(member or self.member).pk])

    def action_url(self, action, member=None):
        return reverse(f"admin:campus_nexus_member_{action}", args=[(member or self.member).pk])

    def login_superuser(self):
        self.client.login(username="root", password="StrongPass123!")

    def test_member_without_user_displays_not_activated_tab(self):
        self.login_superuser()

        response = self.client.get(self.change_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Portal Account")
        self.assertContains(response, "Not Activated")
        self.assertContains(response, "This member does not yet have access")
        self.assertContains(response, "Activate Portal Account")
        self.assertContains(response, "formaction")
        self.assertContains(response, self.action_url("activate_portal_account"))
        self.assertNotContains(response, '<form method="post" action="' + self.action_url("activate_portal_account"))
        self.assertContains(response, "Profile Photo")
        self.assertContains(response, "Personal Details")
        self.assertContains(response, "Academic Details")
        self.assertContains(response, "Audit")

    def test_activate_action_creates_user_links_member_and_sends_setup_email(self):
        self.login_superuser()

        response = self.client.post(self.action_url("activate_portal_account"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("#portal-account-tab", response["Location"])
        self.member.refresh_from_db()
        self.assertIsNotNone(self.member.user)
        self.assertEqual(self.member.user.email, self.member.email)
        self.assertEqual(self.member.user.first_name, self.member.first_name)
        self.assertFalse(self.member.user.is_staff)
        self.assertFalse(self.member.user.is_superuser)
        self.assertTrue(self.member.user.is_active)
        self.assertFalse(self.member.user.has_usable_password())
        self.assertFalse(self.member.user.check_password(self.member.registration_number))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/reset/", mail.outbox[0].body)
        response = self.client.get(self.change_url())
        self.assertContains(response, "Portal account activated for Ssali Jamil")
        self.assertContains(response, f"Username: {self.member.user.username}")
        self.assertContains(response, "Portal Account Status")
        self.assertContains(response, "Active")
        self.assertContains(response, self.member.user.username)
        self.assertContains(response, "ssalijamal697@gmail.com")

    def test_activation_uses_post_and_get_does_not_activate(self):
        self.login_superuser()

        response = self.client.get(self.action_url("activate_portal_account"))

        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.user_id)

    def test_activation_does_not_duplicate_existing_member_portal_account(self):
        self.login_superuser()
        self.client.post(self.action_url("activate_portal_account"))
        self.member.refresh_from_db()
        user_id = self.member.user_id

        response = self.client.post(self.action_url("activate_portal_account"))

        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.assertEqual(self.member.user_id, user_id)
        self.assertEqual(get_user_model().objects.filter(email__iexact=self.member.email).count(), 1)
        response = self.client.get(self.change_url())
        self.assertContains(response, "A portal account already exists for this member.")

    def test_existing_user_linked_to_another_member_is_rejected(self):
        user_model = get_user_model()
        linked_user = user_model.objects.create_user(
            username="linked.member",
            email=self.member.email,
            password="StrongPass123!",
        )
        Member.objects.create(
            user=linked_user,
            first_name="Other",
            last_name="Member",
            email="other-linked-member@example.com",
            phone="+256700000011",
            registration_number="REG011",
            member_type="student",
        )
        self.login_superuser()

        self.client.post(self.action_url("activate_portal_account"))

        self.member.refresh_from_db()
        self.assertIsNone(self.member.user_id)

    def test_admin_role_account_conflict_is_rejected(self):
        self.member.email = self.assoc_user.email
        self.member.save(update_fields=["email"])
        self.login_superuser()

        self.client.post(self.action_url("activate_portal_account"))

        self.member.refresh_from_db()
        self.assertIsNone(self.member.user_id)

    def test_disable_and_enable_portal_access_toggle_user_active_without_deleting_records(self):
        self.login_superuser()
        self.client.post(self.action_url("activate_portal_account"))
        self.member.refresh_from_db()
        user_id = self.member.user_id

        disable_response = self.client.post(self.action_url("disable_portal_account"))
        self.member.refresh_from_db()
        self.assertEqual(disable_response.status_code, 302)
        self.assertFalse(self.member.user.is_active)
        self.assertTrue(Member.objects.filter(pk=self.member.pk).exists())
        self.assertTrue(get_user_model().objects.filter(pk=user_id).exists())

        enable_response = self.client.post(self.action_url("enable_portal_account"))
        self.member.refresh_from_db()
        self.assertEqual(enable_response.status_code, 302)
        self.assertTrue(self.member.user.is_active)

    def test_dean_and_association_admin_cannot_manage_portal_accounts(self):
        self.client.login(username="dean.portal", password="StrongPass123!")
        dean_response = self.client.post(self.action_url("activate_portal_account"))
        self.assertEqual(dean_response.status_code, 403)

        self.client.logout()
        self.client.login(username="assoc.portal", password="StrongPass123!")
        assoc_response = self.client.post(self.action_url("activate_portal_account"))
        self.assertEqual(assoc_response.status_code, 403)

    def test_audit_log_records_activation_without_password_or_token(self):
        self.login_superuser()

        self.client.post(self.action_url("activate_portal_account"))

        audit = AuditLog.objects.get(action="MEMBER_PORTAL_ACCOUNT_ACTIVATED")
        self.assertEqual(audit.actor, self.superuser)
        metadata = str(audit.metadata).lower()
        self.assertNotIn("password", metadata)
        self.assertNotIn("token", metadata)

    def test_email_failure_keeps_linked_account_and_shows_warning(self):
        self.login_superuser()

        with patch(
            "campus_nexus.services.member_portal_account.send_onboarding_invitation_email",
            side_effect=RuntimeError("SMTP unavailable"),
        ):
            response = self.client.post(self.action_url("activate_portal_account"))

        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.assertIsNotNone(self.member.user_id)
        response = self.client.get(self.change_url())
        self.assertContains(response, "The password setup email could not be sent")
        self.assertContains(response, "SMTP unavailable")

    def test_normal_member_save_still_works_normally(self):
        self.login_superuser()

        response = self.client.post(
            self.change_url(),
            {
                "first_name": "Ssali",
                "last_name": "Jamil",
                "email": "updated.ssalijamal697@gmail.com",
                "phone": "+256700000010",
                "nationality": "",
                "member_type": "student",
                "registration_number": "223-063012-27433",
                "national_id_number": "",
                "faculty": "",
                "course": "",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, "updated.ssalijamal697@gmail.com")
        self.assertIsNone(self.member.user_id)

    def test_linked_member_portal_login_remains_functional(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="portal.member",
            email=self.member.email,
            password="StrongPass123!",
        )
        self.member.user = user
        self.member.save(update_fields=["user"])

        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "portal.member", "password": "StrongPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
