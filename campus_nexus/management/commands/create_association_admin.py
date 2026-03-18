from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from campus_nexus.models import Association, AssociationAdmin
from campus_nexus.services.onboarding import send_onboarding_invitation_email


class Command(BaseCommand):
    help = "Create/update an Association Admin and send onboarding invitation"

    def add_arguments(self, parser):
        parser.add_argument(
            "--manual-password",
            action="store_true",
            help="Prompt for a password and skip invitation email for this run.",
        )
        parser.add_argument(
            "--base-url",
            default=None,
            help="Base URL used for invitation links (defaults to CAMPUS_NEXUS_SITE_URL).",
        )

    @staticmethod
    def _prompt(field_name: str, *, required: bool = True, default: str = "") -> str:
        suffix = f" [{default}]" if default else ""
        value = input(f"{field_name}{suffix}: ").strip()
        if not value:
            value = default
        if required and not value:
            raise CommandError(f"{field_name} is required.")
        return value

    def handle(self, *args, **options):
        User = get_user_model()
        username_field = User.USERNAME_FIELD
        email_field = User.get_email_field_name()
        manual_password = options.get("manual_password", False)
        base_url = options.get("base_url")

        self.stdout.write(self.style.MIGRATE_HEADING("Enter user details:"))
        username = self._prompt(username_field)
        email = self._prompt(email_field)
        first_name = self._prompt("first_name", required=False)
        last_name = self._prompt("last_name", required=False)

        associations = Association.objects.all()
        if not associations.exists():
            raise CommandError("No associations available. Create one first.")

        self.stdout.write("\nAvailable Associations:")
        for assoc in associations:
            self.stdout.write(f"  [{assoc.id}] {assoc.name}")

        while True:
            try:
                assoc_id = int(input("\nSelect association ID: ").strip())
                association = associations.get(pk=assoc_id)
                break
            except (ValueError, Association.DoesNotExist):
                self.stdout.write(self.style.ERROR("Invalid association ID, please try again."))

        lookup = {username_field: username}
        defaults = {email_field: email}
        if hasattr(User, "first_name"):
            defaults["first_name"] = first_name
        if hasattr(User, "last_name"):
            defaults["last_name"] = last_name

        user, created = User.objects.get_or_create(
            **lookup,
            defaults=defaults,
        )

        if created:
            user.set_unusable_password()
            self.stdout.write(self.style.SUCCESS(f"Created user {getattr(user, username_field)}"))
        else:
            if user.is_superuser:
                raise CommandError(
                    "The selected user is a superuser. Use a non-superuser account for Association Admin."
                )
            self.stdout.write(
                self.style.WARNING(
                    f"User {getattr(user, username_field)} already exists, updating profile fields."
                )
            )
            setattr(user, email_field, email)
            if hasattr(user, "first_name"):
                user.first_name = first_name
            if hasattr(user, "last_name"):
                user.last_name = last_name

        if not user.is_staff:
            user.is_staff = True

        if manual_password:
            password = self._prompt("password")
            user.set_password(password)
        user.save()

        assoc_admin, created = AssociationAdmin.objects.update_or_create(
            user=user,
            defaults={"association": association}
        )

        if created:
            self.stdout.write(self.style.SUCCESS(
                f"Created AssociationAdmin for {getattr(user, username_field)} -> {association.name}"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"Updated AssociationAdmin for {getattr(user, username_field)} -> {association.name}"
            ))

        if manual_password:
            self.stdout.write(
                self.style.WARNING(
                    "Manual password mode selected. Invitation email was skipped."
                )
            )
        else:
            try:
                sent = send_onboarding_invitation_email(
                    user=user,
                    invited_by="Campus Nexus Administrator",
                    base_url=base_url,
                )
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"Invitation email failed: {exc}"))
            else:
                if sent:
                    self.stdout.write(self.style.SUCCESS(f"Invitation sent to {user.email}."))
                else:
                    self.stdout.write(
                        self.style.WARNING("Invitation not sent because the user has no email address.")
                    )

        self.stdout.write(self.style.SUCCESS("Done!"))
