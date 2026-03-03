import os
import tempfile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from campus_nexus.models import Course, Faculty, Member


class ImportMembersCsvCommandTests(TestCase):
    def _write_csv(self, content):
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8")
        handle.write(content)
        handle.flush()
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.remove(handle.name))
        return handle.name

    def test_import_creates_member_and_assigns_relations(self):
        faculty = Faculty.objects.create(name="Faculty of Science")
        course = Course.objects.create(name="BSc Computer Science", faculty=faculty, duration_years=3)
        user_model = get_user_model()
        importer = user_model.objects.create_user(
            username="importer",
            email="importer@example.com",
            password="pass12345",
            is_staff=True,
        )

        csv_path = self._write_csv(
            "first_name,last_name,email,phone,registration_number,national_id_number,member_type,faculty,course,nationality\n"
            "Amina,Nabirye,amina@example.com,+256700000100,223-063012-900,CM11111111AA,student,Faculty of Science,BSc Computer Science,Uganda\n"
        )

        call_command("import_members_csv", csv_path, created_by="importer")

        member = Member.objects.get(email="amina@example.com")
        self.assertEqual(member.first_name, "Amina")
        self.assertEqual(member.faculty_id, faculty.id)
        self.assertEqual(member.course_id, course.id)
        self.assertEqual(member.created_by_id, importer.id)
        self.assertEqual(member.nationality, "Uganda")

    def test_dry_run_does_not_commit(self):
        faculty = Faculty.objects.create(name="Faculty of Arts")
        Course.objects.create(name="BA History", faculty=faculty, duration_years=3)

        csv_path = self._write_csv(
            "first_name,last_name,email,phone,registration_number,national_id_number,member_type,faculty,course,nationality\n"
            "John,Doe,john@example.com,+256700000200,223-063012-901,CM22222222BB,student,Faculty of Arts,BA History,Uganda\n"
        )

        call_command("import_members_csv", csv_path, dry_run=True)
        self.assertFalse(Member.objects.filter(email="john@example.com").exists())

