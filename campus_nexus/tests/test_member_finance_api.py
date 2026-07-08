from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from campus_nexus.models import (
    Association,
    AssociationAdmin,
    AssociationPaymentInstruction,
    AuditLog,
    Charge,
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


class MemberFinanceApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="finance.member",
            email="finance.member@example.com",
            password="StrongPass123!",
        )
        self.other_user = user_model.objects.create_user(
            username="finance.other",
            email="finance.other@example.com",
            password="StrongPass123!",
        )
        self.staff_user = user_model.objects.create_user(
            username="finance.staff",
            email="finance.staff@example.com",
            password="StrongPass123!",
            is_staff=True,
        )
        self.association = Association.objects.create(name="Coders Club")
        self.other_association = Association.objects.create(name="Writers Club")
        self.member = Member.objects.create(
            user=self.user,
            first_name="Safia",
            last_name="Nalukwago",
            email="finance.member.profile@example.com",
            phone="+256700001001",
            registration_number="FIN001",
            member_type="student",
        )
        self.other_member = Member.objects.create(
            user=self.other_user,
            first_name="Asha",
            last_name="Kato",
            email="finance.other.profile@example.com",
            phone="+256700001002",
            registration_number="FIN002",
            member_type="student",
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
            description="Annual membership",
            amount_due=Decimal("100000.00"),
            due_date=timezone.localdate() + timezone.timedelta(days=7),
            status="partial",
        )
        self.subscription_charge = Charge.objects.create(
            association=self.association,
            membership=self.membership,
            purpose="subscription_fee",
            title="Subscription",
            amount_due=Decimal("50000.00"),
            status="unpaid",
            is_overdue=True,
        )
        self.cancelled_charge = Charge.objects.create(
            association=self.association,
            membership=self.membership,
            purpose="other",
            title="Cancelled",
            amount_due=Decimal("90000.00"),
            status="cancelled",
        )
        self.other_charge = Charge.objects.create(
            association=self.other_association,
            membership=self.other_membership,
            purpose="membership_fee",
            title="Other Membership Fee",
            amount_due=Decimal("75000.00"),
            status="unpaid",
        )
        self.payment = Payment.objects.create(
            charge=self.charge,
            membership=self.membership,
            amount_paid=Decimal("30000.00"),
            status="recorded",
            payment_method="cash",
            reference_code="REC-001",
        )
        Payment.objects.create(
            charge=self.charge,
            membership=self.membership,
            amount_paid=Decimal("10000.00"),
            status="reversed",
            payment_method="cash",
            reference_code="REV-001",
        )
        self.other_payment = Payment.objects.create(
            charge=self.other_charge,
            membership=self.other_membership,
            amount_paid=Decimal("25000.00"),
            status="recorded",
            payment_method="cash",
            reference_code="OTHER-001",
        )

    def authenticate(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "finance.member", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_finance_summary_uses_own_recorded_financial_truth(self):
        self.authenticate()

        response = self.client.get("/api/v1/finance/summary/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_billed"], "150000.00")
        self.assertEqual(response.data["total_paid"], "30000.00")
        self.assertEqual(response.data["outstanding_balance"], "120000.00")
        self.assertEqual(response.data["payment_completion_percentage"], "20.00")
        self.assertEqual(response.data["charge_counts"]["total"], 2)
        self.assertEqual(response.data["charge_counts"]["partial"], 1)
        self.assertEqual(response.data["charge_counts"]["unpaid"], 1)
        self.assertEqual(response.data["charge_counts"]["overdue"], 1)
        self.assertEqual(response.data["membership_fee_obligations"][0]["balance"], "70000.00")
        self.assertEqual(response.data["recent_payments"][0]["id"], self.payment.pk)

    def test_zero_billed_summary_does_not_divide_by_zero(self):
        self.authenticate()
        Charge.objects.filter(membership=self.membership).delete()
        Payment.objects.filter(membership=self.membership).delete()

        response = self.client.get("/api/v1/finance/summary/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_billed"], "0.00")
        self.assertEqual(response.data["payment_completion_percentage"], "0.00")

    def test_member_sees_only_own_charges_and_detail(self):
        self.authenticate()

        list_response = self.client.get("/api/v1/charges/")
        other_detail = self.client.get(f"/api/v1/charges/{self.other_charge.pk}/")
        own_detail = self.client.get(f"/api/v1/charges/{self.charge.pk}/")

        self.assertEqual(list_response.status_code, 200)
        ids = [item["id"] for item in list_response.data["results"]]
        self.assertIn(self.charge.pk, ids)
        self.assertIn(self.subscription_charge.pk, ids)
        self.assertIn(self.cancelled_charge.pk, ids)
        self.assertNotIn(self.other_charge.pk, ids)
        self.assertEqual(other_detail.status_code, 404)
        self.assertEqual(own_detail.status_code, 200)
        self.assertEqual(own_detail.data["paid_amount"], "30000.00")
        self.assertEqual(own_detail.data["balance"], "70000.00")
        self.assertEqual(own_detail.data["payments"][0]["reference_code"], "REV-001")
        self.assertIsNone(own_detail.data["payment_guidance"])

    def test_payment_instruction_endpoint_scopes_to_own_open_charges(self):
        instruction = AssociationPaymentInstruction.objects.create(
            association=self.association,
            payment_method="cash",
            payment_location="Coders Office, Kampala Campus",
            pay_to="Association Treasurer",
            contact_phone="+256751000000",
            instructions="Present your registration number when paying.",
            is_active=True,
        )
        AssociationPaymentInstruction.objects.create(
            association=self.other_association,
            payment_method="cash",
            payment_location="Other Office",
            pay_to="Other Treasurer",
            contact_phone="+256751000001",
            is_active=True,
        )
        AssociationPaymentInstruction.objects.create(
            association=self.association,
            payment_method="cash",
            payment_location="Old Office",
            pay_to="Former Treasurer",
            contact_phone="+256751000002",
            is_active=False,
        )
        self.authenticate()

        response = self.client.get("/api/v1/payment-instructions/")
        charge_detail = self.client.get(f"/api/v1/charges/{self.charge.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["results"]], [instruction.pk])
        self.assertEqual(response.data["results"][0]["payment_method"], "cash")
        self.assertEqual(response.data["results"][0]["payment_method_display"], "Cash")
        self.assertEqual(charge_detail.status_code, 200)
        self.assertEqual(charge_detail.data["payment_guidance"]["id"], instruction.pk)

    def test_payment_instruction_endpoint_denies_anonymous_and_non_member(self):
        anonymous = self.client.get("/api/v1/payment-instructions/")
        self.assertEqual(anonymous.status_code, 401)

        self.client.force_authenticate(user=self.staff_user)
        non_member = self.client.get("/api/v1/payment-instructions/")
        self.assertEqual(non_member.status_code, 403)

    def test_charge_status_filter_never_widens_member_scope(self):
        self.authenticate()

        response = self.client.get("/api/v1/charges/?status=unpaid")

        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.subscription_charge.pk])

    def test_anonymous_and_non_member_are_denied_charge_access(self):
        anonymous = self.client.get("/api/v1/charges/")
        self.assertEqual(anonymous.status_code, 401)

        self.client.force_authenticate(user=self.staff_user)
        non_member = self.client.get("/api/v1/charges/")
        self.assertEqual(non_member.status_code, 403)

    def test_member_sees_only_own_payments_and_detail(self):
        self.authenticate()

        list_response = self.client.get("/api/v1/payments/")
        other_detail = self.client.get(f"/api/v1/payments/{self.other_payment.pk}/")
        own_detail = self.client.get(f"/api/v1/payments/{self.payment.pk}/")

        self.assertEqual(list_response.status_code, 200)
        ids = [item["id"] for item in list_response.data["results"]]
        self.assertIn(self.payment.pk, ids)
        self.assertNotIn(self.other_payment.pk, ids)
        self.assertEqual(other_detail.status_code, 404)
        self.assertEqual(own_detail.status_code, 200)
        self.assertEqual(own_detail.data["amount"], "30000.00")
        self.assertEqual(own_detail.data["reference_code"], "REC-001")
        self.assertEqual(own_detail.data["charge"]["balance"], "70000.00")

    def test_payment_filters_never_widen_member_scope(self):
        self.authenticate()

        response = self.client.get(f"/api/v1/payments/?association={self.other_association.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_receipt_endpoint_is_scoped_and_documents_no_pdf_support(self):
        self.authenticate()

        own_receipt = self.client.get(f"/api/v1/payments/{self.payment.pk}/receipt/")
        other_receipt = self.client.get(f"/api/v1/payments/{self.other_payment.pk}/receipt/")

        self.assertEqual(own_receipt.status_code, 501)
        self.assertIn("PDF receipt generation is not available", own_receipt.data["detail"])
        self.assertEqual(other_receipt.status_code, 404)

    def test_dashboard_finance_matches_summary(self):
        self.authenticate()

        dashboard = self.client.get("/api/v1/dashboard/")
        summary = self.client.get("/api/v1/finance/summary/")

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(dashboard.data["summary"]["total_paid"], summary.data["total_paid"])
        self.assertEqual(dashboard.data["summary"]["outstanding_balance"], summary.data["outstanding_balance"])


class MemberFinanceActivationRegressionTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.reviewer = self.user_model.objects.create_user(username="finance.reviewer", is_staff=True)
        self.association = Association.objects.create(name="Finance Club")
        self.member = Member.objects.create(
            first_name="Finance",
            last_name="Member",
            email="finance.activation@example.com",
            phone="+256700001003",
            registration_number="FIN003",
            member_type="student",
        )
        Fee.objects.create(association=self.association, fee_type="membership", amount=Decimal("40000.00"))

    def create_approved_application(self):
        application = create_membership_application(member=self.member, association=self.association)
        return approve_membership_application(application=application, reviewed_by=self.reviewer)

    def test_partial_payment_inactive_full_payment_activates(self):
        application = self.create_approved_application()

        Payment.objects.create(
            membership=application.membership,
            charge=application.charge,
            amount_paid=Decimal("10000.00"),
            status="recorded",
        )
        application.refresh_from_db()
        application.membership.refresh_from_db()
        self.assertEqual(application.status, MembershipApplication.STATUS_APPROVED_PENDING_PAYMENT)
        self.assertEqual(application.membership.status, "inactive")

        Payment.objects.create(
            membership=application.membership,
            charge=application.charge,
            amount_paid=Decimal("30000.00"),
            status="recorded",
        )
        application.refresh_from_db()
        application.membership.refresh_from_db()
        self.assertEqual(application.status, MembershipApplication.STATUS_ACTIVE)
        self.assertEqual(application.membership.status, "active")

    def test_charge_core_truth_excludes_reversed_payments(self):
        application = self.create_approved_application()
        charge = application.charge
        Payment.objects.create(
            membership=application.membership,
            charge=charge,
            amount_paid=Decimal("15000.00"),
            status="recorded",
        )
        Payment.objects.create(
            membership=application.membership,
            charge=charge,
            amount_paid=Decimal("25000.00"),
            status="reversed",
        )

        charge.refresh_from_db()
        charge.recompute_status()

        self.assertEqual(charge.amount_paid_total, Decimal("15000.00"))
        self.assertEqual(charge.balance, Decimal("25000.00"))
        self.assertEqual(charge.status, "partial")

    def test_reversal_reopens_membership_payment_requirement(self):
        application = self.create_approved_application()
        payment = Payment.objects.create(
            membership=application.membership,
            charge=application.charge,
            amount_paid=Decimal("40000.00"),
            status="recorded",
            recorded_by=self.reviewer,
        )
        application.refresh_from_db()
        application.membership.refresh_from_db()
        self.assertEqual(application.status, MembershipApplication.STATUS_ACTIVE)
        self.assertEqual(application.membership.status, "active")

        payment.status = "reversed"
        payment.full_clean()
        payment.save(update_fields=["status"])

        application.refresh_from_db()
        application.membership.refresh_from_db()
        application.charge.refresh_from_db()
        self.assertEqual(application.charge.status, "unpaid")
        self.assertEqual(application.charge.amount_paid_total, Decimal("0.00"))
        self.assertEqual(application.charge.balance, Decimal("40000.00"))
        self.assertEqual(application.status, MembershipApplication.STATUS_APPROVED_PENDING_PAYMENT)
        self.assertEqual(application.membership.status, "inactive")
        self.assertTrue(
            AuditLog.objects.filter(
                action="MEMBERSHIP_PAYMENT_REQUIREMENT_REOPENED",
                object_id=str(application.pk),
            ).exists()
        )

    def test_payment_validation_rejects_overpayment_and_cancelled_charge(self):
        application = self.create_approved_application()
        Payment.objects.create(
            membership=application.membership,
            charge=application.charge,
            amount_paid=Decimal("30000.00"),
            status="recorded",
        )

        overpayment = Payment(
            membership=application.membership,
            charge=application.charge,
            amount_paid=Decimal("15000.00"),
            status="recorded",
        )
        with self.assertRaises(ValidationError):
            overpayment.full_clean()

        application.charge.status = "cancelled"
        application.charge.save(update_fields=["status"])
        cancelled_payment = Payment(
            membership=application.membership,
            charge=application.charge,
            amount_paid=Decimal("1000.00"),
            status="recorded",
        )
        with self.assertRaises(ValidationError):
            cancelled_payment.full_clean()

    def test_payment_reference_is_generated_and_unique(self):
        application = self.create_approved_application()
        first = Payment.objects.create(
            membership=application.membership,
            charge=application.charge,
            amount_paid=Decimal("10000.00"),
            status="recorded",
        )
        second = Payment.objects.create(
            membership=application.membership,
            charge=application.charge,
            amount_paid=Decimal("10000.00"),
            status="recorded",
        )

        self.assertTrue(first.reference_code.startswith("PAY-"))
        self.assertTrue(second.reference_code.startswith("PAY-"))
        self.assertNotEqual(first.reference_code, second.reference_code)

        duplicate = Payment(
            membership=application.membership,
            charge=application.charge,
            amount_paid=Decimal("10000.00"),
            status="recorded",
            reference_code=first.reference_code,
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()


class AssociationPaymentInstructionAdminTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.association = Association.objects.create(name="Admin Club")
        self.other_association = Association.objects.create(name="Other Admin Club")
        self.association_admin_user = user_model.objects.create_user(
            username="instruction.admin",
            password="StrongPass123!",
            is_staff=True,
        )
        self.other_admin_user = user_model.objects.create_user(
            username="instruction.other",
            password="StrongPass123!",
            is_staff=True,
        )
        self.dean_user = user_model.objects.create_user(
            username="instruction.dean",
            password="StrongPass123!",
            is_staff=True,
        )
        AssociationAdmin.objects.create(user=self.association_admin_user, association=self.association)
        AssociationAdmin.objects.create(user=self.other_admin_user, association=self.other_association)
        from campus_nexus.models import Dean

        Dean.objects.create(user=self.dean_user)

    def test_association_admin_can_manage_own_cash_instruction(self):
        self.client.force_login(self.association_admin_user)

        response = self.client.post(
            reverse("admin:campus_nexus_associationpaymentinstruction_add"),
            {
                "association": self.association.pk,
                "payment_method": "cash",
                "payment_location": "Admin Club Office",
                "pay_to": "Association Treasurer",
                "contact_phone": "+256751000003",
                "instructions": "Bring your registration number.",
                "is_active": "on",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        instruction = AssociationPaymentInstruction.objects.get()
        self.assertEqual(instruction.association, self.association)

    def test_association_admin_cannot_edit_another_association_instruction(self):
        instruction = AssociationPaymentInstruction.objects.create(
            association=self.other_association,
            payment_method="cash",
            payment_location="Other Office",
            pay_to="Other Treasurer",
            contact_phone="+256751000004",
            is_active=True,
        )
        self.client.force_login(self.association_admin_user)

        response = self.client.get(
            reverse("admin:campus_nexus_associationpaymentinstruction_change", args=[instruction.pk])
        )

        self.assertEqual(response.status_code, 302)

    def test_dean_cannot_manage_payment_instructions(self):
        self.client.force_login(self.dean_user)

        response = self.client.get(reverse("admin:campus_nexus_associationpaymentinstruction_changelist"))

        self.assertEqual(response.status_code, 403)
