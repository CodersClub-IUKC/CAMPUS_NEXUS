from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from campus_nexus.models import Association, AuditLog, Faculty, Member, Membership
from campus_nexus.services.audit import record_audit_event


class AuditLoggingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.superuser = User.objects.create_superuser(
            username="auditor",
            email="auditor@example.com",
            password="pass12345",
        )
        cls.faculty = Faculty.objects.create(name="Faculty of Science")
        cls.association = Association.objects.create(
            name="Audit Association",
            faculty=cls.faculty,
            description="Association for audit tests",
        )
        cls.member = Member.objects.create(
            first_name="Audit",
            last_name="Member",
            email="audit.member@example.com",
            phone="0700000011",
            registration_number="223-063012-999",
            national_id_number="CM00000011ZZ",
            member_type="student",
            faculty=cls.faculty,
        )
        cls.membership = Membership.objects.create(
            member=cls.member,
            association=cls.association,
            status="active",
        )

    def setUp(self):
        self.client.login(username="auditor", password="pass12345")

    def test_fee_creation_is_audited(self):
        url = reverse("admin:campus_nexus_fee_add")
        response = self.client.post(
            url,
            data={
                "association": str(self.association.id),
                "fee_type": "membership",
                "amount": "12000.00",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AuditLog.objects.filter(action="fee_created", model_name="campus_nexus.fee").exists())

    def test_membership_status_change_is_audited(self):
        url = reverse("admin:campus_nexus_membership_change", args=[self.membership.id])
        response = self.client.post(
            url,
            data={
                "member": str(self.member.id),
                "association": str(self.association.id),
                "status": "inactive",
                "subscription_anchor_date": "",
                "_save": "Save",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            AuditLog.objects.filter(
                action="membership_status_changed",
                model_name="campus_nexus.membership",
                object_id=str(self.membership.id),
            ).exists()
        )

    def test_record_audit_event_preserves_unicode_object_repr(self):
        class UnicodeObject:
            pk = "unicode-object"
            _meta = type("Meta", (), {"label_lower": "campus_nexus.unicodeobject"})()

            def __str__(self):
                return "Member Name → Association Name"

        record_audit_event(
            actor=self.superuser,
            action="unicode_object_repr_recorded",
            obj=UnicodeObject(),
            association=self.association,
        )

        audit_log = AuditLog.objects.get(action="unicode_object_repr_recorded")
        self.assertEqual(audit_log.object_repr, "Member Name → Association Name")
