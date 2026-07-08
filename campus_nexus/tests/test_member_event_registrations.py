from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from campus_nexus.models import (
    Association,
    AssociationAdmin,
    AuditLog,
    Dean,
    Event,
    EventRegistration,
    Member,
    MemberNotificationPreference,
    Membership,
    Notification,
)
from campus_nexus.services.event_registration import (
    EventRegistrationError,
    cancel_event_registration,
    register_for_event,
)


class EventRegistrationModelServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="event.member")
        self.association = Association.objects.create(name="Events Club")
        self.member = Member.objects.create(
            user=self.user,
            first_name="Event",
            last_name="Member",
            email="event.member@example.com",
            phone="+256700005001",
            registration_number="EVT001",
            member_type="student",
        )
        self.membership = Membership.objects.create(member=self.member, association=self.association, status="active")
        self.event = Event.objects.create(
            association=self.association,
            title="Django Training Session",
            description="Training",
            event_date=timezone.now() + timezone.timedelta(days=3),
            venue="Lab 1",
            posted_by=self.membership,
        )

    def test_model_relationship_statuses_and_uniqueness(self):
        registration = EventRegistration.objects.create(event=self.event, member=self.member)

        self.assertEqual(registration.status, EventRegistration.STATUS_REGISTERED)
        self.assertIsNotNone(registration.registered_at)
        with self.assertRaises(IntegrityError):
            EventRegistration.objects.create(event=self.event, member=self.member)

    def test_cancel_sets_cancelled_status_and_timestamp(self):
        registration = EventRegistration.objects.create(event=self.event, member=self.member)

        with self.captureOnCommitCallbacks(execute=True):
            cancelled = cancel_event_registration(member=self.member, event=self.event)

        self.assertEqual(cancelled.pk, registration.pk)
        self.assertEqual(cancelled.status, EventRegistration.STATUS_CANCELLED)
        self.assertIsNotNone(cancelled.cancelled_at)
        self.assertTrue(Notification.objects.filter(title="Event Registration Cancelled").exists())

    def test_registration_restore_is_single_row_with_new_confirmation(self):
        with self.captureOnCommitCallbacks(execute=True):
            registration = register_for_event(member=self.member, event=self.event)
        with self.captureOnCommitCallbacks(execute=True):
            cancel_event_registration(member=self.member, event=self.event)
        with self.captureOnCommitCallbacks(execute=True):
            restored = register_for_event(member=self.member, event=self.event)

        self.assertEqual(EventRegistration.objects.filter(event=self.event, member=self.member).count(), 1)
        self.assertEqual(restored.pk, registration.pk)
        self.assertEqual(restored.status, EventRegistration.STATUS_REGISTERED)
        self.assertEqual(Notification.objects.filter(title="Event Registration Confirmed").count(), 2)

    def test_inactive_suspended_unrelated_and_past_events_are_ineligible(self):
        self.membership.status = "inactive"
        self.membership.save(update_fields=["status"])
        with self.assertRaises(EventRegistrationError) as inactive:
            register_for_event(member=self.member, event=self.event)
        self.assertEqual(inactive.exception.code, "active_membership_required")

        self.membership.status = "suspended"
        self.membership.save(update_fields=["status"])
        with self.assertRaises(EventRegistrationError) as suspended:
            register_for_event(member=self.member, event=self.event)
        self.assertEqual(suspended.exception.code, "membership_suspended")

        other_event = Event.objects.create(
            association=Association.objects.create(name="Other Events"),
            title="Other Event",
            description="Other",
            event_date=timezone.now() + timezone.timedelta(days=1),
            venue="Hall",
        )
        with self.assertRaises(EventRegistrationError):
            register_for_event(member=self.member, event=other_event)

        self.membership.status = "active"
        self.membership.save(update_fields=["status"])
        past_event = Event.objects.create(
            association=self.association,
            title="Past Event",
            description="Past",
            event_date=timezone.now() - timezone.timedelta(hours=1),
            venue="Hall",
        )
        with self.assertRaises(EventRegistrationError) as past:
            register_for_event(member=self.member, event=past_event)
        self.assertEqual(past.exception.code, "event_ended")


class EventRegistrationApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="event.api",
            email="event.api@example.com",
            password="StrongPass123!",
        )
        self.other_user = user_model.objects.create_user(username="event.other", password="StrongPass123!")
        self.staff_user = user_model.objects.create_user(username="event.staff", password="StrongPass123!", is_staff=True)
        self.association = Association.objects.create(name="FOSSA")
        self.other_association = Association.objects.create(name="Writers")
        self.member = Member.objects.create(
            user=self.user,
            first_name="API",
            last_name="Member",
            email="event.api.profile@example.com",
            phone="+256700005002",
            registration_number="EVT002",
            member_type="student",
        )
        self.other_member = Member.objects.create(
            user=self.other_user,
            first_name="Other",
            last_name="Member",
            email="event.other.profile@example.com",
            phone="+256700005003",
            registration_number="EVT003",
            member_type="student",
        )
        self.membership = Membership.objects.create(member=self.member, association=self.association, status="active")
        self.other_membership = Membership.objects.create(
            member=self.other_member,
            association=self.association,
            status="active",
        )
        self.event = Event.objects.create(
            association=self.association,
            title="Member Event",
            description="Event",
            event_date=timezone.now() + timezone.timedelta(days=2),
            venue="Main Hall",
            posted_by=self.membership,
        )
        self.other_event = Event.objects.create(
            association=self.other_association,
            title="Other Event",
            description="Other",
            event_date=timezone.now() + timezone.timedelta(days=2),
            venue="Other Hall",
        )

    def authenticate(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "event.api", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_member_can_register_idempotently_and_event_context_updates(self):
        self.authenticate()
        with self.captureOnCommitCallbacks(execute=True):
            first = self.client.post(f"/api/v1/events/{self.event.pk}/register/")
        with self.captureOnCommitCallbacks(execute=True):
            second = self.client.post(f"/api/v1/events/{self.event.pk}/register/")

        detail = self.client.get(f"/api/v1/events/{self.event.pk}/")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(EventRegistration.objects.filter(member=self.member, event=self.event).count(), 1)
        self.assertEqual(Notification.objects.filter(title="Event Registration Confirmed").count(), 1)
        self.assertTrue(detail.data["is_registered"])
        self.assertEqual(detail.data["registration_status"], "registered")
        self.assertFalse(detail.data["actions"]["can_register"])
        self.assertTrue(detail.data["actions"]["can_cancel_registration"])
        self.assertEqual(detail.data["registered_count"], 1)

    def test_ineligible_register_and_auth_guards(self):
        anonymous = self.client.post(f"/api/v1/events/{self.event.pk}/register/")
        self.assertEqual(anonymous.status_code, 401)

        self.client.force_authenticate(user=self.staff_user)
        non_member = self.client.post(f"/api/v1/events/{self.event.pk}/register/")
        self.assertEqual(non_member.status_code, 403)

        self.client.force_authenticate(user=None)
        self.authenticate()
        unrelated = self.client.post(f"/api/v1/events/{self.other_event.pk}/register/")
        self.assertEqual(unrelated.status_code, 400)
        self.assertEqual(unrelated.data["code"], "active_membership_required")

    def test_member_can_cancel_own_registration_idempotently(self):
        self.authenticate()
        registration = EventRegistration.objects.create(event=self.event, member=self.member)
        other_registration = EventRegistration.objects.create(event=self.event, member=self.other_member)

        with self.captureOnCommitCallbacks(execute=True):
            first = self.client.post(f"/api/v1/events/{self.event.pk}/cancel-registration/")
        with self.captureOnCommitCallbacks(execute=True):
            second = self.client.post(f"/api/v1/events/{self.event.pk}/cancel-registration/")

        registration.refresh_from_db()
        other_registration.refresh_from_db()
        detail = self.client.get(f"/api/v1/events/{self.event.pk}/")
        other_detail = self.client.get(f"/api/v1/event-registrations/{other_registration.pk}/")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(registration.status, EventRegistration.STATUS_CANCELLED)
        self.assertIsNotNone(registration.cancelled_at)
        self.assertEqual(other_registration.status, EventRegistration.STATUS_REGISTERED)
        self.assertEqual(other_detail.status_code, 404)
        self.assertFalse(detail.data["is_registered"])
        self.assertEqual(detail.data["registration_status"], "cancelled")
        self.assertTrue(detail.data["actions"]["can_register"])
        self.assertFalse(detail.data["actions"]["can_cancel_registration"])
        self.assertEqual(Notification.objects.filter(title="Event Registration Cancelled").count(), 1)

    def test_cancellation_after_event_start_is_blocked(self):
        self.authenticate()
        past_event = Event.objects.create(
            association=self.association,
            title="Started Event",
            description="Started",
            event_date=timezone.now() - timezone.timedelta(minutes=1),
            venue="Hall",
        )
        EventRegistration.objects.create(event=past_event, member=self.member)

        response = self.client.post(f"/api/v1/events/{past_event.pk}/cancel-registration/")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "event_already_started")

    def test_registration_list_detail_filters_and_safe_fields(self):
        self.authenticate()
        own = EventRegistration.objects.create(event=self.event, member=self.member)
        EventRegistration.objects.create(event=self.event, member=self.other_member)

        list_response = self.client.get("/api/v1/event-registrations/?status=registered")
        detail_response = self.client.get(f"/api/v1/event-registrations/{own.pk}/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([item["id"] for item in list_response.data["results"]], [own.pk])
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["event"]["title"], "Member Event")
        self.assertNotIn("member", detail_response.data)

    def test_event_notification_preference_does_not_suppress_lifecycle_confirmations(self):
        MemberNotificationPreference.objects.create(member=self.member, event_notifications=False)
        self.authenticate()

        with self.captureOnCommitCallbacks(execute=True):
            register = self.client.post(f"/api/v1/events/{self.event.pk}/register/")
        with self.captureOnCommitCallbacks(execute=True):
            cancel = self.client.post(f"/api/v1/events/{self.event.pk}/cancel-registration/")

        self.assertEqual(register.status_code, 200)
        self.assertEqual(cancel.status_code, 200)
        self.assertTrue(Notification.objects.filter(title="Event Registration Confirmed").exists())
        self.assertTrue(Notification.objects.filter(title="Event Registration Cancelled").exists())


class EventRegistrationAdminTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.association = Association.objects.create(name="Admin Events")
        self.other_association = Association.objects.create(name="Other Admin Events")
        self.admin_user = user_model.objects.create_user(username="event.admin", password="StrongPass123!", is_staff=True)
        self.dean_user = user_model.objects.create_user(username="event.dean", password="StrongPass123!", is_staff=True)
        AssociationAdmin.objects.create(user=self.admin_user, association=self.association)
        Dean.objects.create(user=self.dean_user)
        self.member = Member.objects.create(
            first_name="Admin",
            last_name="Member",
            email="admin.event@example.com",
            phone="+256700005004",
            registration_number="EVT004",
            member_type="student",
        )
        membership = Membership.objects.create(member=self.member, association=self.association, status="active")
        self.event = Event.objects.create(
            association=self.association,
            title="Admin Event",
            description="Event",
            event_date=timezone.now() + timezone.timedelta(days=1),
            venue="Hall",
            posted_by=membership,
        )
        self.other_event = Event.objects.create(
            association=self.other_association,
            title="Other Admin Event",
            description="Event",
            event_date=timezone.now() + timezone.timedelta(days=1),
            venue="Hall",
        )
        self.registration = EventRegistration.objects.create(event=self.event, member=self.member)
        self.other_registration = EventRegistration.objects.create(event=self.other_event, member=self.member)

    def test_association_admin_sees_only_own_event_registrations(self):
        self.client.force_login(self.admin_user)

        own = self.client.get(f"/admin/campus_nexus/eventregistration/{self.registration.pk}/change/")
        other = self.client.get(f"/admin/campus_nexus/eventregistration/{self.other_registration.pk}/change/")

        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 302)

    def test_dean_is_read_only(self):
        self.client.force_login(self.dean_user)

        response = self.client.get(f"/admin/campus_nexus/eventregistration/{self.registration.pk}/change/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Event registration")
