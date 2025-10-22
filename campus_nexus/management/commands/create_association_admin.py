from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from campus_nexus.models import (
  Association,
  AssociationAdmin,
  Member,
  Membership,
  Cabinet,
  CabinetMember,
  Fee,
  Payment,
  Event,
)


class Command(BaseCommand):
    help = "Create an Association Admin (staff user tied to an association)"

    def handle(self, *args, **options):
        User = get_user_model()

        user_data = {}
        required_fields = [User.USERNAME_FIELD] + list(User.REQUIRED_FIELDS)

        self.stdout.write(self.style.MIGRATE_HEADING("Enter user details:"))
        for field in required_fields:
            value = input(f"{field}: ").strip()
            user_data[field] = value

        password = input("Password: ").strip()

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

        lookup = {User.USERNAME_FIELD: user_data[User.USERNAME_FIELD]}
        user, created = User.objects.get_or_create(
            **lookup,
            defaults={**{f: v for f, v in user_data.items() if f != User.USERNAME_FIELD}}
        )

        if created:
            user.set_password(password)
            self.stdout.write(self.style.SUCCESS(f"Created user {getattr(user, User.USERNAME_FIELD)}"))
        else:
            self.stdout.write(self.style.WARNING(f"User {getattr(user, User.USERNAME_FIELD)} already exists, updating password/fields"))
            user.set_password(password)
            for f, v in user_data.items():
                setattr(user, f, v)
        user.save()

        assoc_admin, created = AssociationAdmin.objects.update_or_create(
            user=user,
            defaults={"association": association}
        )

        if created:
            self.stdout.write(self.style.SUCCESS(
                f"Created AssociationAdmin for {getattr(user, User.USERNAME_FIELD)} -> {association.name}"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"Updated AssociationAdmin for {getattr(user, User.USERNAME_FIELD)} -> {association.name}"
            ))

        self.stdout.write(self.style.SUCCESS("Done!"))
