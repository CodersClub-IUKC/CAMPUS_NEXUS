from django.test import TestCase

from campus_nexus.admin import FeeAdminForm
from campus_nexus.models import Association, Faculty


class FeeAdminFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.faculty = Faculty.objects.create(name="Faculty of Computing")
        cls.association = Association.objects.create(
            name="Developers Club",
            faculty=cls.faculty,
            description="Testing association",
        )

    def test_form_init_does_not_crash_when_reminder_field_is_excluded(self):
        form = FeeAdminForm()
        self.assertIn("duration_months", form.fields)

    def test_membership_fee_is_valid_with_only_required_membership_fields(self):
        form = FeeAdminForm(
            data={
                "association": str(self.association.id),
                "fee_type": "membership",
                "amount": "15000.00",
            }
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_subscription_fee_requires_subscription_policy_fields(self):
        form = FeeAdminForm(
            data={
                "association": str(self.association.id),
                "fee_type": "subscription",
                "amount": "20000.00",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("duration_months", form.errors)

    def test_subscription_fee_valid_when_required_policy_fields_are_present(self):
        form = FeeAdminForm(
            data={
                "association": str(self.association.id),
                "fee_type": "subscription",
                "amount": "20000.00",
                "duration_months": "4",
                "grace_days": "7",
                "max_missed_cycles": "2",
                "allow_installments": "on",
            }
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())
