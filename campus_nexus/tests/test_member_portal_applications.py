from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from campus_nexus.admin import MembershipApplicationAdmin
from campus_nexus.models import (
    Association,
    AssociationAdmin,
    Charge,
    Dean,
    Faculty,
    Fee,
    Course,
    Member,
    Membership,
    MembershipApplication,
    Payment,
)
from campus_nexus.services.membership_application import (
    MembershipApplicationError,
    activate_membership_if_paid,
    approve_membership_application,
    create_membership_application,
    reject_membership_application,
)


class MemberPortalApplicationApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="student",
            email="student@example.com",
            password="StrongPass123!",
        )
        self.other_user = user_model.objects.create_user(
            username="other",
            email="other@example.com",
            password="StrongPass123!",
        )
        self.staff_user = user_model.objects.create_user(
            username="staff",
            email="staff@example.com",
            password="StrongPass123!",
            is_staff=True,
        )
        self.faculty = Faculty.objects.create(name="Science")
        self.other_faculty = Faculty.objects.create(name="Business")
        self.course = Course.objects.create(name="BIT", faculty=self.faculty, duration_years=3)
        self.academic = Association.objects.create(name="Science Association", faculty=self.faculty)
        self.other_academic = Association.objects.create(name="Another Science Association", faculty=self.faculty)
        self.mismatch_academic = Association.objects.create(name="Business Association", faculty=self.other_faculty)
        self.non_academic = Association.objects.create(name="Coders Club")
        self.other_non_academic = Association.objects.create(name="Debate Club")
        self.member = Member.objects.create(
            user=self.user,
            first_name="Safia",
            last_name="Nalukwago",
            email="safia@example.com",
            phone="+256700000001",
            registration_number="REG001",
            member_type="student",
            faculty=self.faculty,
        )
        self.other_member = Member.objects.create(
            user=self.other_user,
            first_name="Asha",
            last_name="Kato",
            email="asha@example.com",
            phone="+256700000002",
            registration_number="REG002",
            member_type="student",
            faculty=self.faculty,
        )

    def authenticate(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "student", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_member_can_apply_to_eligible_academic_association(self):
        self.authenticate()

        response = self.client.post(
            "/api/v1/membership-applications/",
            {"association": self.academic.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], MembershipApplication.STATUS_PENDING_APPROVAL)
        self.assertEqual(response.data["association"]["id"], self.academic.pk)
        self.assertFalse(Membership.objects.filter(member=self.member, association=self.academic).exists())

    def test_member_with_no_memberships_discovers_associations(self):
        self.authenticate()

        response = self.client.get("/api/v1/associations/")

        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.data["results"]]
        self.assertIn("Science Association", names)
        self.assertIn("Another Science Association", names)
        self.assertIn("Coders Club", names)
        self.assertIn("Debate Club", names)
        self.assertNotIn("Business Association", names)

        science = next(item for item in response.data["results"] if item["name"] == "Science Association")
        self.assertTrue(science["eligibility"]["is_eligible"])
        self.assertTrue(science["actions"]["can_apply"])

    def test_non_academic_association_is_discoverable_across_faculties(self):
        self.member.faculty = self.other_faculty
        self.member.save(update_fields=["faculty"])
        self.authenticate()

        response = self.client.get("/api/v1/associations/")

        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.data["results"]]
        self.assertIn("Coders Club", names)
        self.assertIn("Debate Club", names)
        self.assertIn("Business Association", names)
        self.assertNotIn("Science Association", names)

    def test_course_faculty_is_used_when_member_faculty_is_missing(self):
        self.member.faculty = None
        self.member.course = self.course
        self.member.save(update_fields=["faculty", "course"])
        self.authenticate()

        response = self.client.get("/api/v1/associations/")

        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.data["results"]]
        self.assertIn("Science Association", names)
        self.assertIn("Coders Club", names)
        self.assertNotIn("Business Association", names)

    def test_association_detail_works_before_membership_exists(self):
        self.authenticate()

        response = self.client.get(f"/api/v1/associations/{self.academic.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.academic.pk)
        self.assertIsNone(response.data["current_membership_status"])
        self.assertTrue(response.data["actions"]["can_apply"])

    def test_other_faculty_academic_detail_is_not_discoverable(self):
        self.authenticate()

        response = self.client.get(f"/api/v1/associations/{self.mismatch_academic.pk}/")

        self.assertEqual(response.status_code, 404)

    def test_faculty_mismatch_blocks_academic_application(self):
        self.authenticate()

        response = self.client.post(
            "/api/v1/membership-applications/",
            {"association": self.mismatch_academic.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "academic_faculty_mismatch")

    def test_association_discovery_requires_member_authentication(self):
        anonymous = self.client.get("/api/v1/associations/")
        self.assertEqual(anonymous.status_code, 401)

        self.client.force_authenticate(user=self.staff_user)
        non_member = self.client.get("/api/v1/associations/")
        self.assertEqual(non_member.status_code, 403)

    def test_existing_academic_membership_blocks_another_academic_application(self):
        Membership.objects.create(member=self.member, association=self.academic)
        self.authenticate()

        response = self.client.post(
            "/api/v1/membership-applications/",
            {"association": self.other_academic.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "academic_membership_limit_reached")

    def test_non_academic_applications_are_not_faculty_restricted_and_can_be_multiple(self):
        self.authenticate()

        first = self.client.post(
            "/api/v1/membership-applications/",
            {"association": self.non_academic.pk},
            format="json",
        )
        second = self.client.post(
            "/api/v1/membership-applications/",
            {"association": self.other_non_academic.pk},
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

    def test_duplicate_application_and_existing_membership_are_blocked(self):
        self.authenticate()
        self.client.post(
            "/api/v1/membership-applications/",
            {"association": self.non_academic.pk},
            format="json",
        )

        duplicate = self.client.post(
            "/api/v1/membership-applications/",
            {"association": self.non_academic.pk},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.data["error"]["code"], "application_already_pending")

        MembershipApplication.objects.filter(member=self.member, association=self.non_academic).update(
            status=MembershipApplication.STATUS_CANCELLED
        )
        Membership.objects.create(member=self.member, association=self.non_academic)
        existing = self.client.post(
            "/api/v1/membership-applications/",
            {"association": self.non_academic.pk},
            format="json",
        )
        self.assertEqual(existing.status_code, 400)
        self.assertEqual(existing.data["error"]["code"], "membership_already_exists")

        associations = self.client.get("/api/v1/associations/")
        coders = next(item for item in associations.data["results"] if item["name"] == "Coders Club")
        self.assertEqual(coders["current_membership_status"], "active")
        self.assertFalse(coders["actions"]["can_apply"])

    def test_anonymous_and_non_member_users_cannot_apply(self):
        anonymous = self.client.post(
            "/api/v1/membership-applications/",
            {"association": self.non_academic.pk},
            format="json",
        )
        self.assertEqual(anonymous.status_code, 401)

        self.client.force_authenticate(user=self.staff_user)
        non_member = self.client.post(
            "/api/v1/membership-applications/",
            {"association": self.non_academic.pk},
            format="json",
        )
        self.assertEqual(non_member.status_code, 403)

    def test_application_data_is_current_member_scoped(self):
        own = MembershipApplication.objects.create(member=self.member, association=self.non_academic)
        other = MembershipApplication.objects.create(member=self.other_member, association=self.other_non_academic)
        self.authenticate()

        list_response = self.client.get("/api/v1/membership-applications/?member_id=999")
        other_detail = self.client.get(f"/api/v1/membership-applications/{other.pk}/")
        other_cancel = self.client.post(f"/api/v1/membership-applications/{other.pk}/cancel/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([item["id"] for item in list_response.data["results"]], [own.pk])
        self.assertEqual(other_detail.status_code, 404)
        self.assertEqual(other_cancel.status_code, 404)

    def test_owner_can_cancel_pending_application(self):
        application = MembershipApplication.objects.create(member=self.member, association=self.non_academic)
        self.authenticate()

        response = self.client.post(f"/api/v1/membership-applications/{application.pk}/cancel/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], MembershipApplication.STATUS_CANCELLED)


class MembershipApplicationServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.reviewer = user_model.objects.create_user(
            username="reviewer",
            email="reviewer@example.com",
            password="StrongPass123!",
            is_staff=True,
        )
        self.faculty = Faculty.objects.create(name="Science")
        self.association = Association.objects.create(name="Coders Club")
        self.academic = Association.objects.create(name="Science Association", faculty=self.faculty)
        self.member = Member.objects.create(
            first_name="Safia",
            last_name="Nalukwago",
            email="safia.service@example.com",
            phone="+256700000003",
            registration_number="REG003",
            member_type="student",
            faculty=self.faculty,
        )
        Fee.objects.create(
            association=self.association,
            fee_type="membership",
            amount=Decimal("50000.00"),
        )

    def test_approval_requires_configured_membership_fee(self):
        application = create_membership_application(member=self.member, association=self.academic)

        with self.assertRaises(MembershipApplicationError) as ctx:
            approve_membership_application(application=application, reviewed_by=self.reviewer)

        self.assertEqual(ctx.exception.code, "membership_fee_not_configured")
        self.assertFalse(Membership.objects.filter(member=self.member, association=self.academic).exists())

    def test_approval_creates_inactive_membership_and_fee_charge_once(self):
        application = create_membership_application(member=self.member, association=self.association)

        first = approve_membership_application(application=application, reviewed_by=self.reviewer)
        second = approve_membership_application(application=first, reviewed_by=self.reviewer)

        self.assertEqual(second.status, MembershipApplication.STATUS_APPROVED_PENDING_PAYMENT)
        membership = Membership.objects.get(member=self.member, association=self.association)
        self.assertEqual(membership.status, "inactive")
        self.assertEqual(Charge.objects.filter(membership=membership, purpose="membership_fee").count(), 1)
        self.assertEqual(Membership.objects.filter(member=self.member, association=self.association).count(), 1)

    def test_rejection_requires_reason_and_creates_no_financial_obligation(self):
        application = create_membership_application(member=self.member, association=self.association)

        with self.assertRaises(MembershipApplicationError) as ctx:
            reject_membership_application(application=application, reviewed_by=self.reviewer, reason="")

        self.assertEqual(ctx.exception.code, "rejection_reason_required")
        rejected = reject_membership_application(
            application=application,
            reviewed_by=self.reviewer,
            reason="Not enough information.",
        )
        self.assertEqual(rejected.status, MembershipApplication.STATUS_REJECTED)
        self.assertEqual(rejected.rejection_reason, "Not enough information.")
        self.assertFalse(Membership.objects.filter(member=self.member, association=self.association).exists())
        self.assertEqual(Charge.objects.count(), 0)

    def test_partial_payment_does_not_activate_full_payment_does(self):
        application = approve_membership_application(
            application=create_membership_application(member=self.member, association=self.association),
            reviewed_by=self.reviewer,
        )
        membership = application.membership
        charge = application.charge

        Payment.objects.create(
            membership=membership,
            charge=charge,
            amount_paid=Decimal("20000.00"),
            status="recorded",
            recorded_by=self.reviewer,
        )
        application.refresh_from_db()
        membership.refresh_from_db()
        self.assertEqual(application.status, MembershipApplication.STATUS_APPROVED_PENDING_PAYMENT)
        self.assertEqual(membership.status, "inactive")

        Payment.objects.create(
            membership=membership,
            charge=charge,
            amount_paid=Decimal("30000.00"),
            status="recorded",
            recorded_by=self.reviewer,
        )
        application.refresh_from_db()
        membership.refresh_from_db()
        self.assertEqual(application.status, MembershipApplication.STATUS_ACTIVE)
        self.assertEqual(membership.status, "active")

        activate_membership_if_paid(application=application, actor=self.reviewer)
        self.assertEqual(Membership.objects.filter(member=self.member, association=self.association).count(), 1)

    def test_cancel_approved_application_with_payments_is_blocked(self):
        application = approve_membership_application(
            application=create_membership_application(member=self.member, association=self.association),
            reviewed_by=self.reviewer,
        )
        Payment.objects.create(
            membership=application.membership,
            charge=application.charge,
            amount_paid=Decimal("10000.00"),
            status="recorded",
            recorded_by=self.reviewer,
        )

        from campus_nexus.services.membership_application import cancel_membership_application

        with self.assertRaises(MembershipApplicationError) as ctx:
            cancel_membership_application(application=application, member=self.member)

        self.assertEqual(ctx.exception.code, "application_has_payments")


class MembershipApplicationAdminTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.factory = RequestFactory()
        self.faculty = Faculty.objects.create(name="Science")
        self.own_association = Association.objects.create(name="Coders Club")
        self.other_association = Association.objects.create(name="Debate Club")
        self.own_user = user_model.objects.create_user(
            username="own-admin",
            email="own-admin@example.com",
            password="StrongPass123!",
            is_staff=True,
        )
        self.other_user = user_model.objects.create_user(
            username="other-admin",
            email="other-admin@example.com",
            password="StrongPass123!",
            is_staff=True,
        )
        self.dean_user = user_model.objects.create_user(
            username="dean",
            email="dean@example.com",
            password="StrongPass123!",
            is_staff=True,
        )
        AssociationAdmin.objects.create(user=self.own_user, association=self.own_association)
        AssociationAdmin.objects.create(user=self.other_user, association=self.other_association)
        Dean.objects.create(user=self.dean_user)
        self.member = Member.objects.create(
            first_name="Safia",
            last_name="Nalukwago",
            email="safia.admin@example.com",
            phone="+256700000004",
            registration_number="REG004",
            member_type="student",
            faculty=self.faculty,
        )
        self.own_application = MembershipApplication.objects.create(
            member=self.member,
            association=self.own_association,
        )
        self.other_application = MembershipApplication.objects.create(
            member=self.member,
            association=self.other_association,
        )
        self.model_admin = MembershipApplicationAdmin(MembershipApplication, admin.site)

    def request_for(self, user):
        request = self.factory.get("/admin/campus_nexus/membershipapplication/")
        request.user = user
        return request

    def test_association_admin_queryset_is_scoped_to_own_association(self):
        request = self.request_for(self.own_user)

        queryset = self.model_admin.get_queryset(request)

        self.assertEqual(list(queryset), [self.own_application])

    def test_association_admin_cannot_change_other_association_application(self):
        request = self.request_for(self.own_user)

        self.assertTrue(self.model_admin.has_change_permission(request, self.own_application))
        self.assertFalse(self.model_admin.has_change_permission(request, self.other_application))

    def test_dean_is_read_only(self):
        request = self.request_for(self.dean_user)

        self.assertTrue(self.model_admin.has_view_permission(request, self.own_application))
        self.assertFalse(self.model_admin.has_change_permission(request, self.own_application))
