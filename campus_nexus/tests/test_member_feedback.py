from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from campus_nexus.models import (
    Association,
    AssociationAdmin,
    AuditLog,
    Dean,
    Feedback,
    Member,
    MemberNotificationPreference,
    Membership,
    Notification,
)
from campus_nexus.services.member_feedback import apply_admin_feedback_update


class MemberFeedbackModelTests(TestCase):
    def setUp(self):
        self.member = Member.objects.create(
            first_name="Feedback",
            last_name="Member",
            email="feedback.model@example.com",
            phone="+256700006001",
            registration_number="FDB001",
            member_type="student",
        )

    def test_feedback_defaults_and_validation(self):
        feedback = Feedback(member=self.member, subject="  Help  ", message="  Details  ")
        feedback.full_clean()
        feedback.save()

        self.assertEqual(feedback.category, Feedback.CATEGORY_GENERAL)
        self.assertEqual(feedback.status, Feedback.STATUS_OPEN)
        self.assertEqual(feedback.subject, "Help")
        self.assertEqual(feedback.message, "Details")

        with self.assertRaises(ValidationError):
            Feedback(member=self.member, subject=" ", message="Details").full_clean()
        with self.assertRaises(ValidationError):
            Feedback(member=self.member, subject="Help", message=" ").full_clean()
        with self.assertRaises(ValidationError):
            Feedback(member=self.member, category="bad", subject="Help", message="Details").full_clean()
        with self.assertRaises(ValidationError):
            Feedback(member=self.member, status="bad", subject="Help", message="Details").full_clean()


class MemberFeedbackApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="feedback.member",
            email="feedback.member@example.com",
            password="StrongPass123!",
        )
        self.other_user = user_model.objects.create_user(username="feedback.other", password="StrongPass123!")
        self.staff_user = user_model.objects.create_user(username="feedback.staff", password="StrongPass123!", is_staff=True)
        self.association = Association.objects.create(name="Feedback Club")
        self.other_association = Association.objects.create(name="Other Feedback Club")
        self.member = Member.objects.create(
            user=self.user,
            first_name="Feedback",
            last_name="Member",
            email="feedback.member.profile@example.com",
            phone="+256700006002",
            registration_number="FDB002",
            member_type="student",
        )
        self.other_member = Member.objects.create(
            user=self.other_user,
            first_name="Other",
            last_name="Member",
            email="feedback.other.profile@example.com",
            phone="+256700006003",
            registration_number="FDB003",
            member_type="student",
        )
        Membership.objects.create(member=self.member, association=self.association, status="inactive")

    def authenticate(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "feedback.member", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_member_can_create_feedback_and_notification_audit_are_created(self):
        self.authenticate()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/v1/feedback/",
                {
                    "category": "technical",
                    "association": self.association.pk,
                    "subject": "I cannot view my digital card",
                    "message": "My membership is active but the card page is not loading.",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201)
        feedback = Feedback.objects.get(pk=response.data["id"])
        self.assertEqual(feedback.member, self.member)
        self.assertEqual(feedback.submitted_by, self.user)
        self.assertEqual(feedback.status, Feedback.STATUS_OPEN)
        self.assertEqual(response.data["category_display"], "Technical")
        self.assertEqual(response.data["status_display"], "Open")
        self.assertEqual(response.data["association"]["id"], self.association.pk)
        self.assertEqual(response.data["admin_response"], "")
        self.assertTrue(Notification.objects.filter(title="Feedback Submitted", related_url=f"/feedback/{feedback.pk}").exists())
        self.assertTrue(AuditLog.objects.filter(action="MEMBER_FEEDBACK_SUBMITTED", object_id=str(feedback.pk)).exists())

    def test_create_rejects_unsupported_ownership_and_admin_fields(self):
        self.authenticate()
        for field in ("member_id", "user_id", "status", "admin_response", "responded_by", "responded_at"):
            response = self.client.post(
                "/api/v1/feedback/",
                {
                    "category": "general",
                    "subject": "Help",
                    "message": "Details",
                    field: "1",
                },
                format="json",
            )
            self.assertEqual(response.status_code, 400, field)

    def test_create_rejects_unrelated_association_and_auth_guards(self):
        anonymous = self.client.post("/api/v1/feedback/", {"subject": "Help", "message": "Details"}, format="json")
        self.assertEqual(anonymous.status_code, 401)

        self.client.force_authenticate(user=self.staff_user)
        non_member = self.client.post("/api/v1/feedback/", {"subject": "Help", "message": "Details"}, format="json")
        self.assertEqual(non_member.status_code, 403)

        self.client.force_authenticate(user=None)
        self.authenticate()
        unrelated = self.client.post(
            "/api/v1/feedback/",
            {
                "category": "general",
                "association": self.other_association.pk,
                "subject": "Help",
                "message": "Details",
            },
            format="json",
        )
        self.assertEqual(unrelated.status_code, 400)
        self.assertEqual(unrelated.data["code"], "feedback_association_not_allowed")

    def test_member_list_detail_are_scoped_and_filterable(self):
        self.authenticate()
        first = Feedback.objects.create(member=self.member, subject="First", message="One", status=Feedback.STATUS_RESOLVED)
        second = Feedback.objects.create(member=self.member, subject="Second", message="Two", category=Feedback.CATEGORY_TECHNICAL)
        other = Feedback.objects.create(member=self.other_member, subject="Other", message="Nope")

        list_response = self.client.get("/api/v1/feedback/")
        status_filter = self.client.get("/api/v1/feedback/?status=resolved")
        category_filter = self.client.get("/api/v1/feedback/?category=technical")
        own_detail = self.client.get(f"/api/v1/feedback/{first.pk}/")
        other_detail = self.client.get(f"/api/v1/feedback/{other.pk}/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([item["id"] for item in list_response.data["results"]], [second.pk, first.pk])
        self.assertEqual([item["id"] for item in status_filter.data["results"]], [first.pk])
        self.assertEqual([item["id"] for item in category_filter.data["results"]], [second.pk])
        self.assertEqual(own_detail.status_code, 200)
        self.assertEqual(other_detail.status_code, 404)


class MemberFeedbackAdminServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_user(
            username="feedback.super",
            password="StrongPass123!",
            is_staff=True,
            is_superuser=True,
        )
        self.association_admin_user = user_model.objects.create_user(
            username="feedback.assoc",
            password="StrongPass123!",
            is_staff=True,
        )
        self.dean_user = user_model.objects.create_user(
            username="feedback.dean",
            password="StrongPass123!",
            is_staff=True,
        )
        self.association = Association.objects.create(name="Feedback Admin Club")
        self.other_association = Association.objects.create(name="Other Feedback Admin Club")
        AssociationAdmin.objects.create(user=self.association_admin_user, association=self.association)
        Dean.objects.create(user=self.dean_user)
        self.member_user = user_model.objects.create_user(username="feedback.admin.member")
        self.member = Member.objects.create(
            user=self.member_user,
            first_name="Admin",
            last_name="Feedback",
            email="admin.feedback@example.com",
            phone="+256700006004",
            registration_number="FDB004",
            member_type="student",
        )
        self.feedback = Feedback.objects.create(
            member=self.member,
            association=self.association,
            subject="Need help",
            message="Details",
        )
        self.other_feedback = Feedback.objects.create(
            member=self.member,
            association=self.other_association,
            subject="Other help",
            message="Details",
        )
        self.general_feedback = Feedback.objects.create(member=self.member, subject="General", message="General")

    def test_admin_response_sets_responder_timestamp_audit_and_notification(self):
        self.feedback.status = Feedback.STATUS_IN_REVIEW
        self.feedback.admin_response = "We are checking this."

        with self.captureOnCommitCallbacks(execute=True):
            apply_admin_feedback_update(
                feedback=self.feedback,
                actor=self.superuser,
                old_status=Feedback.STATUS_OPEN,
                old_response="",
            )

        self.feedback.refresh_from_db()
        self.assertEqual(self.feedback.responded_by, self.superuser)
        self.assertIsNotNone(self.feedback.responded_at)
        self.assertTrue(AuditLog.objects.filter(action="MEMBER_FEEDBACK_STATUS_CHANGED").exists())
        self.assertTrue(AuditLog.objects.filter(action="MEMBER_FEEDBACK_RESPONDED").exists())
        self.assertTrue(Notification.objects.filter(title="Feedback Updated", related_url=f"/feedback/{self.feedback.pk}").exists())

        notification_count = Notification.objects.count()
        with self.captureOnCommitCallbacks(execute=True):
            apply_admin_feedback_update(
                feedback=self.feedback,
                actor=self.superuser,
                old_status=self.feedback.status,
                old_response=self.feedback.admin_response,
            )
        self.assertEqual(Notification.objects.count(), notification_count)

    def test_feedback_notifications_ignore_optional_preferences(self):
        MemberNotificationPreference.objects.create(
            member=self.member,
            event_notifications=False,
            announcement_notifications=False,
        )
        with self.captureOnCommitCallbacks(execute=True):
            self.feedback.admin_response = "Mandatory lifecycle update."
            apply_admin_feedback_update(
                feedback=self.feedback,
                actor=self.superuser,
                old_status=self.feedback.status,
                old_response="",
            )
        self.assertTrue(Notification.objects.filter(title="Feedback Updated").exists())

    def test_admin_rbac_scoping(self):
        self.client.force_login(self.association_admin_user)
        own = self.client.get(reverse("admin:campus_nexus_feedback_change", args=[self.feedback.pk]))
        other = self.client.get(reverse("admin:campus_nexus_feedback_change", args=[self.other_feedback.pk]))
        general = self.client.get(reverse("admin:campus_nexus_feedback_change", args=[self.general_feedback.pk]))

        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 302)
        self.assertEqual(general.status_code, 302)

        self.client.force_login(self.dean_user)
        dean = self.client.get(reverse("admin:campus_nexus_feedback_change", args=[self.feedback.pk]))
        self.assertEqual(dean.status_code, 200)
