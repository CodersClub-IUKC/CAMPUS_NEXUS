from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from campus_nexus.models import (
    Announcement,
    Association,
    Event,
    Faculty,
    Fee,
    Member,
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
from campus_nexus.services.notifications import create_member_notification


class NotificationServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="notify.member",
            email="notify.member@example.com",
            password="StrongPass123!",
        )
        self.member = Member.objects.create(
            user=self.user,
            first_name="Notify",
            last_name="Member",
            email="notify.profile@example.com",
            phone="+256700002001",
            registration_number="NOT001",
            member_type="student",
        )

    def test_notification_can_be_created_for_linked_member_user(self):
        notification = create_member_notification(
            member=self.member,
            title="Hello",
            message="Welcome.",
            notification_type="system",
            related_url="/dashboard",
            deduplication_key="hello_once",
        )

        self.assertIsNotNone(notification)
        self.assertEqual(notification.recipient, self.user)
        self.assertEqual(notification.related_url, "/dashboard")

    def test_member_without_user_is_skipped_safely(self):
        legacy_member = Member.objects.create(
            first_name="Legacy",
            last_name="Member",
            email="legacy.notify@example.com",
            phone="+256700002002",
            registration_number="NOT002",
            member_type="student",
        )

        notification = create_member_notification(
            member=legacy_member,
            title="Skipped",
            message="No portal account.",
            notification_type="system",
        )

        self.assertIsNone(notification)
        self.assertEqual(Notification.objects.count(), 0)

    def test_notification_validates_type_and_relative_url(self):
        with self.assertRaises(ValidationError):
            create_member_notification(
                member=self.member,
                title="Bad",
                message="Bad type.",
                notification_type="not-a-type",
            )
        with self.assertRaises(ValidationError):
            create_member_notification(
                member=self.member,
                title="Bad URL",
                message="Absolute URLs are not allowed.",
                notification_type="system",
                related_url="https://example.com/dashboard",
            )

    def test_deduplication_key_prevents_duplicate_state_transition_notification(self):
        first = create_member_notification(
            member=self.member,
            title="Once",
            message="Only once.",
            notification_type="system",
            deduplication_key="state_once",
        )
        second = create_member_notification(
            member=self.member,
            title="Once",
            message="Only once.",
            notification_type="system",
            deduplication_key="state_once",
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Notification.objects.count(), 1)


class NotificationLifecycleTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.reviewer = user_model.objects.create_user(username="notify.reviewer", is_staff=True)
        self.user = user_model.objects.create_user(
            username="notify.lifecycle",
            email="notify.lifecycle@example.com",
            password="StrongPass123!",
        )
        self.association = Association.objects.create(name="FOSSA")
        self.member = Member.objects.create(
            user=self.user,
            first_name="Lifecycle",
            last_name="Member",
            email="notify.lifecycle.profile@example.com",
            phone="+256700002003",
            registration_number="NOT003",
            member_type="student",
        )
        Fee.objects.create(association=self.association, fee_type="membership", amount=Decimal("20000.00"))

    def test_application_lifecycle_notifications(self):
        with self.captureOnCommitCallbacks(execute=True):
            application = create_membership_application(member=self.member, association=self.association)
        self.assertTrue(Notification.objects.filter(title="Application Submitted").exists())

        with self.captureOnCommitCallbacks(execute=True):
            approve_membership_application(application=application, reviewed_by=self.reviewer)

        approved = Notification.objects.get(title="Application Approved")
        self.assertIn("Payment of the required membership fee", approved.message)
        self.assertEqual(approved.related_url, f"/applications/{application.pk}")

    def test_rejection_notification_includes_visible_reason(self):
        application = create_membership_application(member=self.member, association=self.association)

        with self.captureOnCommitCallbacks(execute=True):
            reject_membership_application(
                application=application,
                reviewed_by=self.reviewer,
                reason="Capacity is full.",
            )

        notification = Notification.objects.get(title="Application Not Approved")
        self.assertIn("Capacity is full.", notification.message)

    def test_payment_and_membership_notifications(self):
        application = approve_membership_application(
            application=create_membership_application(member=self.member, association=self.association),
            reviewed_by=self.reviewer,
        )

        with self.captureOnCommitCallbacks(execute=True):
            first_payment = Payment.objects.create(
                membership=application.membership,
                charge=application.charge,
                amount_paid=Decimal("5000.00"),
                status="recorded",
                payment_method="cash",
            )

        recorded = Notification.objects.get(deduplication_key=f"payment_{first_payment.pk}_recorded")
        self.assertEqual(recorded.title, "Payment Recorded")
        self.assertIn("cash payment", recorded.message)
        self.assertEqual(recorded.related_url, f"/payments/{first_payment.pk}")

        with self.captureOnCommitCallbacks(execute=True):
            Payment.objects.create(
                membership=application.membership,
                charge=application.charge,
                amount_paid=Decimal("15000.00"),
                status="recorded",
                payment_method="cash",
            )

        application.refresh_from_db()
        self.assertEqual(application.status, MembershipApplication.STATUS_ACTIVE)
        self.assertTrue(Notification.objects.filter(title="Membership Active").exists())

        first_payment.status = "reversed"
        with self.captureOnCommitCallbacks(execute=True):
            first_payment.save(update_fields=["status"])

        reversed_notice = Notification.objects.get(deduplication_key=f"payment_{first_payment.pk}_reversed")
        self.assertEqual(reversed_notice.title, "Payment Reversed")
        self.assertIn("no longer counts", reversed_notice.message)
        self.assertTrue(Notification.objects.filter(title="Payment Required Again", related_url="/finance").exists())

    def test_separate_payments_create_separate_notifications(self):
        application = approve_membership_application(
            application=create_membership_application(member=self.member, association=self.association),
            reviewed_by=self.reviewer,
        )

        with self.captureOnCommitCallbacks(execute=True):
            Payment.objects.create(
                membership=application.membership,
                charge=application.charge,
                amount_paid=Decimal("10000.00"),
                status="recorded",
            )
            Payment.objects.create(
                membership=application.membership,
                charge=application.charge,
                amount_paid=Decimal("10000.00"),
                status="recorded",
            )

        self.assertEqual(Notification.objects.filter(title="Payment Recorded").count(), 2)

    def test_portal_account_activation_creates_welcome_once(self):
        legacy_member = Member.objects.create(
            first_name="Portal",
            last_name="Welcome",
            email="portal.welcome@example.com",
            phone="+256700002004",
            registration_number="NOT004",
            member_type="student",
        )

        with self.captureOnCommitCallbacks(execute=True):
            activate_member_portal_account(member=legacy_member, activated_by=self.reviewer)

        self.assertEqual(Notification.objects.filter(title="Welcome to Campus Nexus").count(), 1)

    def test_event_creation_and_announcement_publication_create_notifications(self):
        membership = Membership.objects.create(member=self.member, association=self.association, status="active")

        with self.captureOnCommitCallbacks(execute=True):
            event = Event.objects.create(
                association=self.association,
                title="Django Training Session",
                description="Training",
                event_date=timezone.now() + timezone.timedelta(days=3),
                venue="Lab 1",
                posted_by=membership,
            )

        self.assertTrue(Notification.objects.filter(title="New Event", related_url=f"/events/{event.pk}").exists())

        with self.captureOnCommitCallbacks(execute=True):
            announcement = Announcement.objects.create(
                title="Training Schedule Updated",
                message="Bring laptops.",
                audience="association",
                association=self.association,
                is_published=True,
                posted_by=self.reviewer,
            )
        self.assertTrue(
            Notification.objects.filter(
                title="New Announcement",
                related_url=f"/announcements/{announcement.pk}",
            ).exists()
        )

        with self.captureOnCommitCallbacks(execute=True):
            announcement.message = "Edited."
            announcement.save(update_fields=["message"])
        self.assertEqual(Notification.objects.filter(related_url=f"/announcements/{announcement.pk}").count(), 1)


class NotificationApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="notify.api",
            email="notify.api@example.com",
            password="StrongPass123!",
        )
        self.other_user = user_model.objects.create_user(
            username="notify.other",
            email="notify.other@example.com",
            password="StrongPass123!",
        )
        self.staff_user = user_model.objects.create_user(username="notify.staff", password="StrongPass123!", is_staff=True)
        self.member = Member.objects.create(
            user=self.user,
            first_name="API",
            last_name="Member",
            email="notify.api.profile@example.com",
            phone="+256700002005",
            registration_number="NOT005",
            member_type="student",
        )
        self.other_member = Member.objects.create(
            user=self.other_user,
            first_name="Other",
            last_name="Member",
            email="notify.other.profile@example.com",
            phone="+256700002006",
            registration_number="NOT006",
            member_type="student",
        )
        self.old_notification = create_member_notification(
            member=self.member,
            title="Old",
            message="Older.",
            notification_type="system",
            related_url="/dashboard",
            deduplication_key="old",
        )
        self.new_notification = create_member_notification(
            member=self.member,
            title="New",
            message="Newer.",
            notification_type="payment",
            related_url="/payments/1",
            deduplication_key="new",
        )
        self.other_notification = create_member_notification(
            member=self.other_member,
            title="Other",
            message="Other user.",
            notification_type="system",
            deduplication_key="other",
        )

    def authenticate(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "notify.api", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_member_lists_own_notifications_newest_first(self):
        self.authenticate()

        response = self.client.get("/api/v1/notifications/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["results"]], [self.new_notification.pk, self.old_notification.pk])
        self.assertNotIn(self.other_notification.pk, [item["id"] for item in response.data["results"]])
        self.assertNotIn("deduplication_key", response.data["results"][0])
        self.assertEqual(response.data["results"][0]["related_url"], "/payments/1")

    def test_notification_auth_guards(self):
        anonymous = self.client.get("/api/v1/notifications/")
        self.assertEqual(anonymous.status_code, 401)

        self.client.force_authenticate(user=self.staff_user)
        non_member = self.client.get("/api/v1/notifications/")
        self.assertEqual(non_member.status_code, 403)

    def test_unread_count_mark_read_and_read_all_are_scoped(self):
        self.authenticate()

        unread = self.client.get("/api/v1/notifications/unread-count/")
        self.assertEqual(unread.data["unread_count"], 2)

        read = self.client.post(f"/api/v1/notifications/{self.new_notification.pk}/read/")
        repeated = self.client.post(f"/api/v1/notifications/{self.new_notification.pk}/read/")
        unread_after_one = self.client.get("/api/v1/notifications/unread-count/")

        self.assertEqual(read.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertTrue(read.data["is_read"])
        self.assertEqual(unread_after_one.data["unread_count"], 1)

        other_read = self.client.post(f"/api/v1/notifications/{self.other_notification.pk}/read/")
        self.assertEqual(other_read.status_code, 404)

        read_all = self.client.post("/api/v1/notifications/read-all/")
        self.assertEqual(read_all.status_code, 200)
        self.assertEqual(read_all.data["updated_count"], 1)
        self.assertFalse(Notification.objects.get(pk=self.other_notification.pk).is_read)

    def test_member_can_retrieve_own_notification_detail(self):
        self.authenticate()

        own = self.client.get(f"/api/v1/notifications/{self.new_notification.pk}/")
        other = self.client.get(f"/api/v1/notifications/{self.other_notification.pk}/")

        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.data["id"], self.new_notification.pk)
        self.assertEqual(other.status_code, 404)
