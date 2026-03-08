import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from campus_nexus.countries import COUNTRY_LOOKUP
from campus_nexus.models import Course, Faculty, Member


class Command(BaseCommand):
    help = "Import or update members from an ERP CSV export."

    REQUIRED_COLUMNS = ("first_name", "last_name", "email", "phone", "member_type")
    COLUMN_ALIASES = {
        "first_name": ("first_name", "firstname", "given_name"),
        "last_name": ("last_name", "lastname", "surname"),
        "email": ("email", "email_address"),
        "phone": ("phone", "phone_number", "mobile"),
        "registration_number": ("registration_number", "reg_no", "registration_no"),
        "national_id_number": ("national_id_number", "nin", "national_id"),
        "member_type": ("member_type", "type"),
        "faculty": ("faculty", "faculty_name"),
        "course": ("course", "course_name", "programme"),
        "nationality": ("nationality", "country"),
    }
    MEMBER_TYPE_MAP = {
        "student": "student",
        "alumni": "alumni",
        "external": "external",
    }

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to CSV file exported from ERP.")
        parser.add_argument(
            "--created-by",
            dest="created_by",
            type=str,
            default="",
            help="Username to stamp into Member.created_by.",
        )
        parser.add_argument(
            "--create-missing-relations",
            action="store_true",
            help="Create missing faculties/courses encountered in CSV rows.",
        )
        parser.add_argument(
            "--default-course-duration-years",
            type=int,
            default=3,
            help="Duration used when creating a course that does not exist.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and simulate import without committing changes.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"]).expanduser().resolve()
        if not csv_path.exists() or not csv_path.is_file():
            raise CommandError(f"CSV file not found: {csv_path}")

        created_by = self._resolve_created_by(options["created_by"])
        create_missing_relations = bool(options["create_missing_relations"])
        default_course_duration_years = int(options["default_course_duration_years"])
        dry_run = bool(options["dry_run"])

        created_count = 0
        updated_count = 0
        skipped_count = 0
        failure_messages: list[str] = []

        with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames:
                raise CommandError("CSV has no header row.")

            missing_required_headers = [
                column
                for column in self.REQUIRED_COLUMNS
                if not any(alias in reader.fieldnames for alias in self.COLUMN_ALIASES[column])
            ]
            if missing_required_headers:
                raise CommandError(
                    "CSV is missing required column(s): " + ", ".join(missing_required_headers)
                )

            with transaction.atomic():
                for line_number, row in enumerate(reader, start=2):
                    try:
                        member, created = self._upsert_member(
                            row=row,
                            created_by=created_by,
                            create_missing_relations=create_missing_relations,
                            default_course_duration_years=default_course_duration_years,
                        )
                        if created:
                            created_count += 1
                        else:
                            updated_count += 1
                    except ValueError as exc:
                        skipped_count += 1
                        failure_messages.append(f"Line {line_number}: {exc}")
                    except ValidationError as exc:
                        skipped_count += 1
                        failure_messages.append(f"Line {line_number}: {exc}")
                    except Exception as exc:
                        skipped_count += 1
                        failure_messages.append(f"Line {line_number}: {exc}")

                if dry_run:
                    transaction.set_rollback(True)

        mode = "DRY-RUN" if dry_run else "COMMITTED"
        self.stdout.write(self.style.SUCCESS(f"{mode} import summary"))
        self.stdout.write(f"Created: {created_count}")
        self.stdout.write(f"Updated: {updated_count}")
        self.stdout.write(f"Skipped: {skipped_count}")

        if failure_messages:
            self.stdout.write(self.style.WARNING("Skipped row details:"))
            for message in failure_messages:
                self.stdout.write(f" - {message}")

    def _resolve_created_by(self, username):
        if not username:
            return None
        user_model = get_user_model()
        try:
            return user_model.objects.get(username=username)
        except user_model.DoesNotExist as exc:
            raise CommandError(f"User for --created-by was not found: {username}") from exc

    def _upsert_member(self, row, created_by, create_missing_relations, default_course_duration_years):
        first_name = self._value(row, "first_name")
        last_name = self._value(row, "last_name")
        email = self._value(row, "email").lower()
        phone = self._normalize_phone(self._value(row, "phone"))

        member_type_raw = self._value(row, "member_type").lower()
        member_type = self.MEMBER_TYPE_MAP.get(member_type_raw)
        if not member_type:
            raise ValueError(f"Unsupported member_type '{member_type_raw}'.")

        registration_number = self._value(row, "registration_number")
        national_id_number = self._value(row, "national_id_number")
        nationality = self._normalize_country(self._value(row, "nationality"))

        faculty = self._resolve_faculty(
            name=self._value(row, "faculty"),
            create_missing_relations=create_missing_relations,
        )
        course = self._resolve_course(
            name=self._value(row, "course"),
            faculty=faculty,
            create_missing_relations=create_missing_relations,
            default_course_duration_years=default_course_duration_years,
        )

        lookup_kwargs = {}
        if registration_number:
            lookup_kwargs["registration_number"] = registration_number
        elif email:
            lookup_kwargs["email"] = email
        else:
            raise ValueError("Row must include registration_number or email for upsert matching.")

        member = Member.objects.filter(**lookup_kwargs).first()
        created = member is None
        if created:
            member = Member(**lookup_kwargs)

        member.first_name = first_name
        member.last_name = last_name
        member.email = email
        member.phone = phone
        member.registration_number = registration_number or None
        member.national_id_number = national_id_number or None
        member.member_type = member_type
        member.faculty = faculty
        member.course = course
        member.nationality = nationality

        if created and created_by:
            member.created_by = created_by

        member.full_clean()
        member.save()
        return member, created

    def _resolve_faculty(self, name, create_missing_relations):
        if not name:
            return None
        faculty = Faculty.objects.filter(name__iexact=name).first()
        if faculty:
            return faculty
        if not create_missing_relations:
            raise ValueError(
                f"Faculty '{name}' does not exist. Use --create-missing-relations to auto-create it."
            )
        return Faculty.objects.create(name=name)

    def _resolve_course(self, name, faculty, create_missing_relations, default_course_duration_years):
        if not name:
            return None

        queryset = Course.objects.filter(name__iexact=name)
        if faculty:
            queryset = queryset.filter(faculty=faculty)

        course = queryset.first()
        if course:
            return course

        if not create_missing_relations:
            raise ValueError(
                f"Course '{name}' does not exist. Use --create-missing-relations to auto-create it."
            )

        if not faculty:
            raise ValueError(
                f"Course '{name}' cannot be created without faculty value in the same CSV row."
            )

        return Course.objects.create(
            name=name,
            faculty=faculty,
            duration_years=max(1, default_course_duration_years),
        )

    def _value(self, row, field):
        aliases = self.COLUMN_ALIASES[field]
        for alias in aliases:
            if alias in row and row[alias] is not None:
                return str(row[alias]).strip()
        return ""

    def _normalize_phone(self, value):
        if not value:
            return ""
        cleaned = value.replace(" ", "").replace("-", "")
        if cleaned.startswith("00"):
            cleaned = "+" + cleaned[2:]
        return cleaned

    def _normalize_country(self, value):
        if not value:
            return ""
        return COUNTRY_LOOKUP.get(value.lower(), "")

