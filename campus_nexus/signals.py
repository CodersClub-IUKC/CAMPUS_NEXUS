from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction

from .models import AssociationAdmin, Guild, Payment, Membership
from campus_nexus.services.membership_emails import (
    send_membership_assigned_email,
    send_membership_removed_email,
)


@receiver(post_save, sender=AssociationAdmin)
def add_association_admin_model_permissions(sender, instance: AssociationAdmin, created: bool, **kwargs):
    """
    Ensure that when an AssociationAdmin is created, they are granted all necessary permissions
    for managing association-related models.
    """
    if created:
        user = instance.user
        association = instance.association

        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from .models import Association, Member, Membership, Cabinet, CabinetMember, Fee, Payment, Event

        user.is_staff = True
        user.is_superuser = False
        user.save()

        # List of models related to the association
        models = [Association, Member, Membership, Cabinet, CabinetMember, Fee, Payment, Event]

        for model in models:
            ct = ContentType.objects.get_for_model(model)
            perms = Permission.objects.filter(content_type=ct)
            user.user_permissions.add(*perms)

@receiver(post_save, sender=Guild)
def add_guild_model_permissions(sender, instance: Guild, created: bool, **kwargs):
    """
    Ensure that when a Guild is created, its user is granted all necessary permissions
    for managing guild-related models.
    """
    print("="*100)
    print(f"Guild signal triggered for {instance.user.username}")
    if created:
        user = instance.user

        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from .models import Association, Member, Membership, Cabinet, CabinetMember, Fee, Payment, Event

        user.is_staff = True
        user.is_superuser = False
        user.save()

        # List of models related to the guild
        models = [Association, Member, Membership, Cabinet, CabinetMember, Fee, Payment, Event]

        for model in models:
            ct = ContentType.objects.get_for_model(model)
            perms = Permission.objects.filter(content_type=ct)
            user.user_permissions.add(*perms)

@receiver([post_save, post_delete], sender=Payment)
def recompute_charge_after_payment(sender, instance: Payment, **kwargs):
    charge = instance.charge
    charge.recompute_status()
    charge.save(update_fields=["status"])


@receiver(post_save, sender=Payment)
def send_payment_recorded_email(sender, instance: Payment, created: bool, **kwargs):
    # Only send when first created (not edits)
    if not created:
        return

    member = instance.membership.member
    if not member.email:
        return

    association = instance.membership.association
    amount = instance.amount_paid
    purpose = ""
    if getattr(instance, "charge_id", None) and instance.charge:
        purpose = instance.charge.title or instance.charge.get_purpose_display()

    subject = "Payment Received - Campus Nexus"
    message = (
        f"Hello {member.full_name},\n\n"
        f"Your payment has been recorded successfully in Campus Nexus.\n\n"
        f"Association: {association.name}\n"
        f"Amount: UGX {amount}\n"
        f"Purpose: {purpose or 'N/A'}\n"
        f"Method: {instance.get_payment_method_display() if hasattr(instance, 'get_payment_method_display') else instance.payment_method}\n"
        f"Date Recorded: {instance.recorded_at if hasattr(instance, 'recorded_at') else instance.payment_date}\n\n"
        f"Thank you.\n"
        f"Campus Nexus"
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [member.email],
        fail_silently=False,
    )
    

@receiver(post_save, sender=Membership)
def membership_created_email(sender, instance: Membership, created, **kwargs):
    if not created:
        return

    member = instance.member
    association = instance.association

    transaction.on_commit(
        lambda: send_membership_assigned_email(
            member=member,
            association=association,
            membership=instance,
        )
    )


@receiver(post_delete, sender=Membership)
def membership_removed_email(sender, instance: Membership, **kwargs):
    member = instance.member
    association = instance.association

    transaction.on_commit(
        lambda: send_membership_removed_email(
            member=member,
            association=association,
        )
    )
