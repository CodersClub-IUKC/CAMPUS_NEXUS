from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from campus_nexus.models import Association, AssociationAdmin, Course, Faculty, Member, Membership
from campus_nexus.services.import_export.centre import (
    build_preview,
    commit_preview,
    export_csv_response,
    export_excel_response,
    get_spec,
    modules_for_request,
)


class ImportExportCentreServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            username="root",
            email="root@example.com",
            password="pass12345",
        )
        self.faculty = Faculty.objects.create(name="Faculty of Science")
        self.course = Course.objects.create(name="BSc Computer Science", faculty=self.faculty, duration_years=3)
        self.association = Association.objects.create(name="Computing Association", faculty=self.faculty)
        self.request = SimpleNamespace(user=self.superuser, session={})

    def _upload(self, content, name="members.csv"):
        return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")

    def test_member_import_previews_then_commits_valid_rows(self):
        upload = self._upload(
            "Registration Number,first_name,last_name,email,phone,member_type,faculty,course,nationality\n"
            "223-063012-900,Amina,Nabirye,amina@example.com,+256700000100,student,Faculty of Science,BSc Computer Science,Uganda\n"
        )

        preview = build_preview(self.request, "members", upload, "create")

        self.assertEqual(preview["counts"]["creates"], 1)
        self.assertEqual(preview["counts"]["invalid"], 0)
        self.assertFalse(Member.objects.filter(email="amina@example.com").exists())

        summary = commit_preview(self.request, preview)

        self.assertEqual(summary["created"], 1)
        self.assertTrue(Member.objects.filter(email="amina@example.com").exists())

    def test_duplicate_member_is_skipped_in_create_only_mode(self):
        Member.objects.create(
            first_name="Amina",
            last_name="Nabirye",
            email="amina@example.com",
            phone="+256700000100",
            registration_number="223-063012-900",
            member_type="student",
            faculty=self.faculty,
            course=self.course,
        )
        upload = self._upload(
            "registration_number,first_name,last_name,email,phone,member_type\n"
            "223-063012-900,Amina,Nabirye,amina@example.com,+256700000100,student\n"
        )

        preview = build_preview(self.request, "members", upload, "create")

        self.assertEqual(preview["counts"]["duplicates"], 1)
        self.assertEqual(preview["counts"]["valid"], 0)

    def test_association_admin_exports_only_own_memberships(self):
        user_model = get_user_model()
        assoc_user = user_model.objects.create_user(
            username="assoc-admin",
            email="assoc-admin@example.com",
            password="pass12345",
            is_staff=True,
        )
        AssociationAdmin.objects.create(user=assoc_user, association=self.association)
        other_association = Association.objects.create(name="Other Association")
        member = Member.objects.create(
            first_name="Amina",
            last_name="Nabirye",
            email="amina@example.com",
            phone="+256700000100",
            registration_number="223-063012-900",
            member_type="student",
            faculty=self.faculty,
            course=self.course,
        )
        Membership.objects.create(member=member, association=self.association)
        Membership.objects.create(member=member, association=other_association)
        request = SimpleNamespace(user=assoc_user)

        response = export_csv_response(request, "memberships")
        body = response.content.decode("utf-8")

        self.assertIn("Computing Association", body)
        self.assertNotIn("Other Association", body)

    def test_centre_hides_member_module_from_association_admins(self):
        user_model = get_user_model()
        assoc_user = user_model.objects.create_user(
            username="limited-admin",
            email="limited-admin@example.com",
            password="pass12345",
            is_staff=True,
        )
        AssociationAdmin.objects.create(user=assoc_user, association=self.association)
        request = SimpleNamespace(user=assoc_user)

        sections = modules_for_request(request)
        visible_keys = {module["key"] for modules in sections.values() for module in modules}

        self.assertNotIn("members", visible_keys)
        self.assertIn("memberships", visible_keys)
        self.assertFalse(get_spec("charges").importable)

    def test_excel_template_export_returns_workbook(self):
        response = export_excel_response(self.request, "members", template=True)

        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertGreater(len(response.content), 100)
