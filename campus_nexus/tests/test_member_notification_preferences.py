from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from campus_nexus.models import (
    Announcement,
    Association,
    AuditLog,
    Event,
    Fee,
    Member,
    MemberNotificationPreference,
    Membership,
    MembershipApplication,
    Notification,
    Payment,
)
from campus_nexus.services.member_portal_account import activate_member_portal_account
from campus_nexus.services.membership_application import (
    approve_membership_application,
    create_membership_application,
    reject_membership_application,
)
from campus_nexus.services.notification_preferences import is_optional_notification_enabled
from campus_nexus.services.notifications import create_member_notification


class MemberNotificationPreferenceModelTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="pref.member", password="StrongPass123!")
        self.member = Member.objects.create(
            user=self.user,
            first_name="Pref",
            last_name="Member",
            email="pref.member@example.com",
            phone="+256700003001",
            registration_number="PREF001",
            member_type="student",
        )

    def test_preference_defaults_and_uniqueness(self):
        preferences = MemberNotificationPreference.objects.create(member=self.member)

        self.assertTrue(preferences.event_notifications)
        self.assertTrue(preferences.announcement_notifications)
        duplicate = MemberNotificationPreference(member=self.member)
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_missing_preference_row_uses_enabled_defaults(self):
        self.assertFalse(hasattr(self.member, "notification_preferences"))
        self.assertTrue(is_optional_notification_enabled(self.member, "events"))
        self.assertTrue(is_optional_notification_enabled(self.member, "announcements"))


class MemberNotificationPreferenceApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="pref.api",
            email="pref.api@example.com",
            password="StrongPass123!",
        )
        self.other_user = user_model.objects.create_user(username="pref.other", password="StrongPass123!")
        self.staff_user = user_model.objects.create_user(username="pref.staff", password="StrongPass123!", is_staff=True)
        self.member = Member.objects.create(
            user=self.user,
            first_name="API",
            last_name="Prefs",
            email="pref.api.profile@example.com",
            phone="+256700003002",
            registration_number="PREF002",
            member_type="student",
        )
        self.other_member = Member.objects.create(
            user=self.other_user,
            first_name="Other",
            last_name="Prefs",
            email="pref.other.profile@example.com",
            phone="+256700003003",
            registration_number="PREF003",
            member_type="student",
        )

    def authenticate(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "pref.api", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_member_can_get_and_patch_own_preferences(self):
        self.authenticate()

        get_response = self.client.get("/api/v1/notification-preferences/")
        patch_response = self.client.patch(
            "/api/v1/notification-preferences/",
            {"event_notifications": False},
            format="json",
        )
        second_patch = self.client.patch(
            "/api/v1/notification-preferences/",
            {"event_notifications": True, "announcement_notifications": False},
            format="json",
        )

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.data, {"event_notifications": True, "announcement_notifications": True})
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data, {"event_notifications": False, "announcement_notifications": True})
        self.assertEqual(second_patch.status_code, 200)
        self.assertEqual(second_patch.data, {"event_notifications": True, "announcement_notifications": False})
        self.assertEqual(MemberNotificationPreference.objects.count(), 1)

    def test_unsupported_preference_keys_are_rejected(self):
        self.authenticate()

        payment = self.client.patch(
            "/api/v1/notification-preferences/",
            {"payment_notifications": False},
            format="json",
        )
        membership = self.client.patch(
            "/api/v1/notification-preferences/",
            {"membership_notifications": False},
            format="json",
        )

        self.assertEqual(payment.status_code, 400)
        self.assertEqual(membership.status_code, 400)

    def test_api_auth_guards(self):
        anonymous = self.client.get("/api/v1/notification-preferences/")
        self.assertEqual(anonymous.status_code, 401)

        self.client.force_authenticate(user=self.staff_user)
        non_member = self.client.get("/api/v1/notification-preferences/")
        self.assertEqual(non_member.status_code, 403)

    def test_audit_event_only_for_actual_changes(self):
        self.authenticate()

        changed = self.client.patch(
            "/api/v1/notification-preferences/",
            {"event_notifications": False},
            format="json",
        )
        noop = self.client.patch(
            "/api/v1/notification-preferences/",
            {"event_notifications": False},
            format="json",
        )

        self.assertEqual(changed.status_code, 200)
        self.assertEqual(noop.status_code, 200)
        self.assertEqual(AuditLog.objects.filter(action="NOTIFICATION_PREFERENCES_UPDATED").count(), 1)


class MemberNotificationPreferencePolicyTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.reviewer = user_model.objects.create_user(username="pref.reviewer", is_staff=True)
        self.user = user_model.objects.create_user(
            username="pref.policy",
            email="pref.policy@example.com",
            password="StrongPass123!",
        )
        self.association = Association.objects.create(name="Preference Club")
        self.application_association = Association.objects.create(name="Application Preference Club")
        self.rejection_association = Association.objects.create(name="Rejection Preference Club")
        self.member = Member.objects.create(
            user=self.user,
            first_name="Policy",
            last_name="Member",
            email="pref.policy.profile@example.com",
            phone="+256700003004",
            registration_number="PREF004",
            member_type="student",
        )
        self.membership = Membership.objects.create(member=self.member, association=self.association, status="active")
        Fee.objects.create(association=self.application_association, fee_type="membership", amount=Decimal("20000.00"))

    def authenticate(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "pref.policy", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def create_event(self, title):
        return Event.objects.create(
            association=self.association,
            title=title,
            description="Training",
            event_date=timezone.now() + timezone.timedelta(days=3),
            venue="Lab",
            posted_by=self.membership,
        )

    def create_announcement(self, title):
        return Announcement.objects.create(
            title=title,
            message="Notice",
            audience="association",
            association=self.association,
            is_published=True,
            posted_by=self.reviewer,
        )

    def test_event_preference_suppresses_future_notifications_only(self):
        with self.captureOnCommitCallbacks(execute=True):
            first_event = self.create_event("Event A")
        self.assertTrue(Notification.objects.filter(related_url=f"/events/{first_event.pk}").exists())

        MemberNotificationPreference.objects.create(member=self.member, event_notifications=False)
        with self.captureOnCommitCallbacks(execute=True):
            second_event = self.create_event("Event B")
        self.assertFalse(Notification.objects.filter(related_url=f"/events/{second_event.pk}").exists())
        self.assertTrue(Notification.objects.filter(related_url=f"/events/{first_event.pk}").exists())

        self.authenticate()
        event_detail = self.client.get(f"/api/v1/events/{second_event.pk}/")
        self.assertEqual(event_detail.status_code, 200)

        preferences = self.member.notification_preferences
        preferences.event_notifications = True
        preferences.save(update_fields=["event_notifications"])
        with self.captureOnCommitCallbacks(execute=True):
            third_event = self.create_event("Event C")
        self.assertTrue(Notification.objects.filter(related_url=f"/events/{third_event.pk}").exists())
        self.assertFalse(Notification.objects.filter(related_url=f"/events/{second_event.pk}").exists())

    def test_announcement_preference_suppresses_future_notifications_only(self):
        with self.captureOnCommitCallbacks(execute=True):
            first = self.create_announcement("Announcement A")
        self.assertTrue(Notification.objects.filter(related_url=f"/announcements/{first.pk}").exists())

        MemberNotificationPreference.objects.create(member=self.member, announcement_notifications=False)
        with self.captureOnCommitCallbacks(execute=True):
            second = self.create_announcement("Announcement B")
        self.assertFalse(Notification.objects.filter(related_url=f"/announcements/{second.pk}").exists())
        self.assertTrue(Notification.objects.filter(related_url=f"/announcements/{first.pk}").exists())

        self.authenticate()
        announcement_detail = self.client.get(f"/api/v1/announcements/{second.pk}/")
        self.assertEqual(announcement_detail.status_code, 200)

        preferences = self.member.notification_preferences
        preferences.announcement_notifications = True
        preferences.save(update_fields=["announcement_notifications"])
        with self.captureOnCommitCallbacks(execute=True):
            third = self.create_announcement("Announcement C")
        self.assertTrue(Notification.objects.filter(related_url=f"/announcements/{third.pk}").exists())
        self.assertFalse(Notification.objects.filter(related_url=f"/announcements/{second.pk}").exists())

    def test_mandatory_notifications_ignore_optional_preferences(self):
        MemberNotificationPreference.objects.create(
            member=self.member,
            event_notifications=False,
            announcement_notifications=False,
        )

        with self.captureOnCommitCallbacks(execute=True):
            application = create_membership_application(member=self.member, association=self.application_association)
        self.assertTrue(Notification.objects.filter(title="Application Submitted").exists())

        with self.captureOnCommitCallbacks(execute=True):
            approved = approve_membership_application(application=application, reviewed_by=self.reviewer)
        self.assertTrue(Notification.objects.filter(title="Application Approved").exists())

        with self.captureOnCommitCallbacks(execute=True):
            payment = Payment.objects.create(
                membership=approved.membership,
                charge=approved.charge,
                amount_paid=Decimal("20000.00"),
                status="recorded",
                payment_method="cash",
            )
        self.assertTrue(Notification.objects.filter(title="Payment Recorded").exists())
        self.assertTrue(Notification.objects.filter(title="Membership Active").exists())

        payment.status = "reversed"
        with self.captureOnCommitCallbacks(execute=True):
            payment.save(update_fields=["status"])
        self.assertTrue(Notification.objects.filter(title="Payment Reversed").exists())
        self.assertTrue(Notification.objects.filter(title="Payment Required Again").exists())

        rejection_application = create_membership_application(member=self.member, association=self.rejection_association)
        with self.captureOnCommitCallbacks(execute=True):
            reject_membership_application(
                application=rejection_application,
                reviewed_by=self.reviewer,
                reason="Not eligible now.",
            )
        self.assertTrue(Notification.objects.filter(title="Application Not Approved").exists())

        legacy_member = Member.objects.create(
            first_name="Welcome",
            last_name="Member",
            email="pref.welcome@example.com",
            phone="+256700003005",
            registration_number="PREF005",
            member_type="student",
        )
        MemberNotificationPreference.objects.create(
            member=legacy_member,
            event_notifications=False,
            announcement_notifications=False,
        )
        with self.captureOnCommitCallbacks(execute=True):
            activate_member_portal_account(member=legacy_member, activated_by=self.reviewer)
        self.assertTrue(Notification.objects.filter(title="Welcome to Campus Nexus").exists())

        system_notification = create_member_notification(
            member=self.member,
            title="System Notice",
            message="Mandatory.",
            notification_type="system",
            deduplication_key="system_notice",
        )
        self.assertIsNotNone(system_notification)
