from decimal import Decimal
import uuid

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from rest_framework.test import APITestCase

from campus_nexus.admin import MembershipAdmin
from campus_nexus.models import (
    Association,
    AuditLog,
    Fee,
    Member,
    Membership,
    MembershipApplication,
    Payment,
)
from campus_nexus.services.membership_application import (
    approve_membership_application,
    create_membership_application,
)
from campus_nexus.services.membership_cards import (
    mask_registration_number,
    rotate_membership_verification_token,
)


class DigitalMembershipCardServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.actor = user_model.objects.create_user(username="card.actor", is_staff=True, is_superuser=True)
        self.association = Association.objects.create(name="Card Club")
        self.member = Member.objects.create(
            first_name="Card",
            last_name="Member",
            email="card.member@example.com",
            phone="+256700004001",
            registration_number="223-063012-27433",
            member_type="student",
        )

    def test_new_memberships_receive_unique_non_personal_tokens(self):
        first = Membership.objects.create(member=self.member, association=self.association, status="active")
        other_member = Member.objects.create(
            first_name="Other",
            last_name="Card",
            email="card.other@example.com",
            phone="+256700004002",
            registration_number="223-063012-27434",
            member_type="student",
        )
        second = Membership.objects.create(member=other_member, association=self.association, status="active")

        self.assertIsInstance(first.verification_token, uuid.UUID)
        self.assertNotEqual(first.verification_token, second.verification_token)
        self.assertNotEqual(str(first.verification_token), str(first.pk))
        self.assertNotEqual(str(first.verification_token), self.member.registration_number)
        self.assertNotEqual(str(first.verification_token), self.member.email)

    def test_token_rotation_changes_token_invalidates_old_lookup_and_audits(self):
        membership = Membership.objects.create(member=self.member, association=self.association, status="active")
        old_token = membership.verification_token

        rotated = rotate_membership_verification_token(membership=membership, actor=self.actor)

        self.assertNotEqual(old_token, rotated.verification_token)
        self.assertFalse(Membership.objects.filter(verification_token=old_token).exists())
        self.assertTrue(Membership.objects.filter(verification_token=rotated.verification_token).exists())
        self.assertTrue(AuditLog.objects.filter(action="MEMBERSHIP_VERIFICATION_TOKEN_ROTATED").exists())

    def test_registration_number_masking(self):
        self.assertEqual(mask_registration_number("223-063012-27433"), "223-******-27433")

    def test_admin_form_does_not_expose_editable_verification_token(self):
        membership = Membership.objects.create(member=self.member, association=self.association, status="active")
        request = RequestFactory().get("/")
        request.user = self.actor
        model_admin = MembershipAdmin(Membership, admin.site)
        form_class = model_admin.get_form(request, obj=membership, change=True)

        self.assertNotIn("verification_token", form_class.base_fields)
        self.assertIn("verification_token_display", model_admin.get_readonly_fields(request, membership))


class DigitalMembershipCardApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.reviewer = user_model.objects.create_user(username="card.reviewer", is_staff=True)
        self.user = user_model.objects.create_user(
            username="card.member",
            email="card.member.user@example.com",
            password="StrongPass123!",
        )
        self.other_user = user_model.objects.create_user(
            username="card.other",
            email="card.other.user@example.com",
            password="StrongPass123!",
        )
        self.staff_user = user_model.objects.create_user(username="card.staff", password="StrongPass123!", is_staff=True)
        self.association = Association.objects.create(
            name="FOSSA",
            theme_primary_color="#123456",
            theme_secondary_color="#abcdef",
            theme_version="themev1",
        )
        self.member = Member.objects.create(
            user=self.user,
            first_name="Ssali",
            last_name="Jamil",
            email="ssali@example.com",
            phone="+256700004003",
            registration_number="223-063012-27433",
            member_type="student",
        )
        self.other_member = Member.objects.create(
            user=self.other_user,
            first_name="Other",
            last_name="Member",
            email="other.card@example.com",
            phone="+256700004004",
            registration_number="223-063012-27435",
            member_type="student",
        )
        self.membership = Membership.objects.create(member=self.member, association=self.association, status="active")
        self.inactive_membership = Membership.objects.create(
            member=self.member,
            association=Association.objects.create(name="Inactive Club"),
            status="inactive",
        )
        self.other_membership = Membership.objects.create(
            member=self.other_member,
            association=self.association,
            status="active",
        )

    def authenticate(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "card.member", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_membership_list_and_detail_expose_card_available_only(self):
        self.authenticate()

        list_response = self.client.get("/api/v1/memberships/")
        detail_response = self.client.get(f"/api/v1/memberships/{self.membership.pk}/")

        self.assertEqual(list_response.status_code, 200)
        first = next(item for item in list_response.data if item["id"] == self.membership.pk)
        inactive = next(item for item in list_response.data if item["id"] == self.inactive_membership.pk)
        self.assertTrue(first["card_available"])
        self.assertFalse(inactive["card_available"])
        self.assertNotIn("verification_token", first)
        self.assertEqual(detail_response.status_code, 200)
        self.assertTrue(detail_response.data["card_available"])
        self.assertNotIn("verification_path", detail_response.data)

    def test_member_can_retrieve_own_active_card(self):
        self.authenticate()

        response = self.client.get(f"/api/v1/memberships/{self.membership.pk}/card/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["membership"]["status"], "active")
        self.assertEqual(str(response.data["membership"]["member_since"]), self.membership.joined_at.date().isoformat())
        self.assertEqual(response.data["member"]["full_name"], "Ssali Jamil")
        self.assertEqual(response.data["member"]["registration_number"], "223-063012-27433")
        self.assertIsNone(response.data["member"]["profile_photo"])
        self.assertEqual(response.data["association"]["name"], "FOSSA")
        self.assertEqual(response.data["association"]["theme"]["primary_color"], "#123456")
        self.assertTrue(response.data["card"]["available"])
        self.assertEqual(response.data["card"]["verification_token"], str(self.membership.verification_token))
        self.assertEqual(response.data["card"]["verification_path"], f"/verify/membership/{self.membership.verification_token}")

    def test_inactive_card_response_hides_token(self):
        self.authenticate()

        response = self.client.get(f"/api/v1/memberships/{self.inactive_membership.pk}/card/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["card"]["available"])
        self.assertIsNone(response.data["card"]["verification_token"])
        self.assertIsNone(response.data["card"]["verification_path"])

    def test_card_endpoint_is_member_scoped(self):
        anonymous = self.client.get(f"/api/v1/memberships/{self.membership.pk}/card/")
        self.assertEqual(anonymous.status_code, 401)

        self.client.force_authenticate(user=self.staff_user)
        non_member = self.client.get(f"/api/v1/memberships/{self.membership.pk}/card/")
        self.assertEqual(non_member.status_code, 403)

        self.client.force_authenticate(user=self.user)
        other = self.client.get(f"/api/v1/memberships/{self.other_membership.pk}/card/")
        self.assertEqual(other.status_code, 404)

    def test_public_verification_active_inactive_and_unknown_privacy(self):
        active = self.client.get(f"/api/v1/public/membership-verification/{self.membership.verification_token}/")
        inactive = self.client.get(
            f"/api/v1/public/membership-verification/{self.inactive_membership.verification_token}/"
        )
        unknown = self.client.get(f"/api/v1/public/membership-verification/{uuid.uuid4()}/")
        sequential = self.client.get(f"/api/v1/public/membership-verification/{self.membership.pk}/")

        self.assertEqual(active.status_code, 200)
        self.assertTrue(active.data["valid"])
        self.assertEqual(active.data["member"]["display_name"], "Ssali Jamil")
        self.assertEqual(active.data["member"]["registration_number"], "223-******-27433")
        self.assertNotIn("email", str(active.data).lower())
        self.assertNotIn("phone", str(active.data).lower())
        self.assertNotIn("payment", str(active.data).lower())
        self.assertNotIn("user", str(active.data).lower())
        self.assertEqual(inactive.status_code, 200)
        self.assertFalse(inactive.data["valid"])
        self.assertIsNone(inactive.data["member"])
        self.assertNotIn("outstanding", str(inactive.data).lower())
        self.assertEqual(unknown.status_code, 404)
        self.assertFalse(unknown.data["valid"])
        self.assertEqual(sequential.status_code, 404)

    def test_live_status_truth_after_reversal_and_repayment(self):
        association = Association.objects.create(name="Live Truth Club")
        Fee.objects.create(association=association, fee_type="membership", amount=Decimal("20000.00"))
        application = approve_membership_application(
            application=create_membership_application(member=self.member, association=association),
            reviewed_by=self.reviewer,
        )
        payment = Payment.objects.create(
            membership=application.membership,
            charge=application.charge,
            amount_paid=Decimal("20000.00"),
            status="recorded",
            payment_method="cash",
        )
        application.refresh_from_db()
        token = application.membership.verification_token
        active = self.client.get(f"/api/v1/public/membership-verification/{token}/")
        self.assertTrue(active.data["valid"])

        payment.status = "reversed"
        payment.save(update_fields=["status"])
        inactive = self.client.get(f"/api/v1/public/membership-verification/{token}/")
        self.assertFalse(inactive.data["valid"])

        Payment.objects.create(
            membership=application.membership,
            charge=application.charge,
            amount_paid=Decimal("20000.00"),
            status="recorded",
            payment_method="cash",
        )
        valid_again = self.client.get(f"/api/v1/public/membership-verification/{token}/")
        self.assertTrue(valid_again.data["valid"])
        application.membership.refresh_from_db()
        self.assertEqual(token, application.membership.verification_token)
