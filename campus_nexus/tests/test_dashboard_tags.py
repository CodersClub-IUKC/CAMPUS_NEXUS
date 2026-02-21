from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.client import RequestFactory

from campus_nexus.models import Association, AssociationAdmin, Charge, Faculty, Member, Membership, Payment
from campus_nexus.templatetags.dashboard_tags import association_dashboard_data


class AssociationDashboardDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.faculty = Faculty.objects.create(name="Faculty of Science")
        cls.association = Association.objects.create(
            name="Association A",
            faculty=cls.faculty,
            description="A",
        )

        cls.user = User.objects.create_user(
            username="assocA",
            email="assocA@example.com",
            password="pass12345",
            is_staff=True,
        )
        cls.assoc_admin = AssociationAdmin.objects.create(user=cls.user, association=cls.association)

        cls.member = Member.objects.create(
            first_name="Ibrahim",
            last_name="Sabavuma",
            email="ibrahim@example.com",
            phone="0700000001",
            registration_number="223-063012-002",
            national_id_number="CM12345678AA",
            member_type="student",
            faculty=cls.faculty,
        )
        cls.membership = Membership.objects.create(
            association=cls.association,
            member=cls.member,
            status="active",
        )

        cls.charge_unpaid = Charge.objects.create(
            association=cls.association,
            membership=cls.membership,
            purpose="membership_fee",
            title="Membership",
            amount_due=Decimal("100.00"),
            status="unpaid",
            is_overdue=True,
        )
        cls.charge_partial = Charge.objects.create(
            association=cls.association,
            membership=cls.membership,
            purpose="subscription_fee",
            title="Subscription",
            amount_due=Decimal("200.00"),
            status="partial",
            is_overdue=False,
        )

        Payment.objects.create(
            charge=cls.charge_partial,
            membership=cls.membership,
            amount_paid=Decimal("50.00"),
            status="recorded",
        )
        Payment.objects.create(
            charge=cls.charge_partial,
            membership=cls.membership,
            amount_paid=Decimal("20.00"),
            status="reversed",
        )

    def test_association_dashboard_data_includes_finance_metrics(self):
        request = RequestFactory().get("/admin/")
        request.user = self.user
        data = association_dashboard_data({"request": request})

        finance = data["finance"]
        self.assertEqual(finance["total_billed"], Decimal("300.00"))
        self.assertEqual(finance["total_collected"], Decimal("50.00"))
        self.assertEqual(finance["outstanding_balance"], Decimal("250.00"))
        self.assertEqual(finance["open_charges_count"], 2)
        self.assertEqual(finance["overdue_charges_count"], 1)
