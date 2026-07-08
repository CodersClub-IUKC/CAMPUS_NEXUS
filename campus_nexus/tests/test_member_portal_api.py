from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from campus_nexus.models import (
    Announcement,
    Association,
    Charge,
    Event,
    Faculty,
    Member,
    Membership,
    Payment,
)


class MemberPortalApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.member_user = user_model.objects.create_user(
            username="member.user",
            email="member@example.com",
            password="StrongPass123!",
        )
        self.staff_user = user_model.objects.create_user(
            username="staff.user",
            email="staff@example.com",
            password="StrongPass123!",
            is_staff=True,
        )

        self.faculty = Faculty.objects.create(name="Science")
        self.other_faculty = Faculty.objects.create(name="Business")
        self.association = Association.objects.create(name="Coders Club", faculty=None)
        self.other_association = Association.objects.create(name="Accounting Club", faculty=self.other_faculty)

        self.member = Member.objects.create(
            user=self.member_user,
            first_name="Safia",
            last_name="Nalukwago",
            email="member-profile@example.com",
            phone="+256700000001",
            registration_number="REG001",
            member_type="student",
            faculty=self.faculty,
        )
        self.other_member = Member.objects.create(
            first_name="Other",
            last_name="Student",
            email="other-profile@example.com",
            phone="+256700000002",
            registration_number="REG002",
            member_type="student",
            faculty=self.other_faculty,
        )

        self.membership = Membership.objects.create(member=self.member, association=self.association)
        self.other_membership = Membership.objects.create(
            member=self.other_member,
            association=self.other_association,
        )
        self.charge = Charge.objects.create(
            association=self.association,
            membership=self.membership,
            purpose="membership_fee",
            title="Membership Fee",
            amount_due=Decimal("100000.00"),
            status="partial",
        )
        Payment.objects.create(
            charge=self.charge,
            membership=self.membership,
            amount_paid=Decimal("25000.00"),
            status="recorded",
        )

        Event.objects.create(
            association=self.association,
            title="Member Event",
            description="Visible to member",
            event_date=timezone.now() + timezone.timedelta(days=3),
            venue="Main Hall",
            posted_by=self.membership,
        )
        Event.objects.create(
            association=self.other_association,
            title="Other Event",
            description="Hidden from member",
            event_date=timezone.now() + timezone.timedelta(days=3),
            venue="Other Hall",
            posted_by=self.other_membership,
        )
        Announcement.objects.create(
            title="Visible Announcement",
            message="For member association",
            audience="association",
            association=self.association,
            is_published=True,
        )
        Announcement.objects.create(
            title="Hidden Announcement",
            message="For other association",
            audience="association",
            association=self.other_association,
            is_published=True,
        )

    def authenticate_member(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "member.user", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return response

    def test_member_login_returns_tokens_and_current_member(self):
        response = self.authenticate_member()

        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["role"], "member")
        self.assertEqual(response.data["user"]["member"]["registration_number"], "REG001")

    def test_staff_without_member_profile_cannot_login_to_member_portal(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "staff.user", "password": "StrongPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("member portal profile", str(response.data).lower())

    def test_profile_requires_linked_member_profile(self):
        self.client.force_authenticate(user=self.staff_user)

        response = self.client.get("/api/v1/profile/")

        self.assertEqual(response.status_code, 403)

    def test_member_profile_endpoint_returns_only_current_member(self):
        self.authenticate_member()

        response = self.client.get("/api/v1/profile/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "member-profile@example.com")
        self.assertEqual(response.data["registration_number"], "REG001")

    def test_memberships_are_current_member_scoped(self):
        self.authenticate_member()

        list_response = self.client.get("/api/v1/memberships/")
        other_detail_response = self.client.get(f"/api/v1/memberships/{self.other_membership.pk}/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]["id"], self.membership.pk)
        self.assertEqual(list_response.data[0]["total_paid"], "25000.00")
        self.assertEqual(list_response.data[0]["outstanding_balance"], "75000.00")
        self.assertEqual(other_detail_response.status_code, 404)

    def test_events_and_announcements_are_member_scoped(self):
        self.authenticate_member()

        events_response = self.client.get("/api/v1/events/")
        announcements_response = self.client.get("/api/v1/announcements/")

        self.assertEqual(events_response.status_code, 200)
        self.assertEqual([item["title"] for item in events_response.data["results"]], ["Member Event"])
        self.assertEqual(announcements_response.status_code, 200)
        self.assertEqual(
            [item["title"] for item in announcements_response.data["results"]],
            ["Visible Announcement"],
        )

    def test_dashboard_uses_existing_financial_state_without_cross_member_data(self):
        self.authenticate_member()

        response = self.client.get("/api/v1/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"]["membership_count"], 1)
        self.assertEqual(response.data["summary"]["total_paid"], "25000.00")
        self.assertEqual(response.data["summary"]["outstanding_balance"], "75000.00")
        self.assertEqual(response.data["upcoming_events"][0]["title"], "Member Event")

