from django.dispatch import receiver
from django.db.models import Q
from django.db.models.signals import pre_save, post_save, post_delete
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction

from .models import Announcement, AssociationAdmin, Event, Guild, Member, Payment, Membership
from campus_nexus.services.membership_emails import (
    send_membership_assigned_email,
    send_membership_removed_email,
)
from campus_nexus.services.notifications import format_ugx, notify_member_on_commit, notify_members_on_commit
from campus_nexus.services.notification_preferences import PREFERENCE_ANNOUNCEMENTS, PREFERENCE_EVENTS


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
        from .models import Association, AssociationPaymentInstruction, Member, Membership, MembershipApplication, Cabinet, CabinetMember, Fee, Payment, Event

        user.is_staff = True
        user.is_superuser = False
        user.save()

        # List of models related to the association
        models = [Association, AssociationPaymentInstruction, Member, Membership, MembershipApplication, Cabinet, CabinetMember, Fee, Payment, Event]

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
    if created:
        user = instance.user

        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from .models import Association, AssociationPaymentInstruction, Member, Membership, MembershipApplication, Cabinet, CabinetMember, Fee, Payment, Event

        user.is_staff = True
        user.is_superuser = False
        user.save()

        # List of models related to the guild
        models = [Association, AssociationPaymentInstruction, Member, Membership, MembershipApplication, Cabinet, CabinetMember, Fee, Payment, Event]

        for model in models:
            ct = ContentType.objects.get_for_model(model)
            perms = Permission.objects.filter(content_type=ct)
            user.user_permissions.add(*perms)

@receiver([post_save, post_delete], sender=Payment)
def recompute_charge_after_payment(sender, instance: Payment, **kwargs):
    charge_id = instance.charge_id
    if charge_id is None:
        return
    from campus_nexus.models import Charge

    charge = Charge.objects.filter(pk=charge_id).first()
    if charge is None:
        return
    from campus_nexus.services.membership_application import sync_membership_payment_state_for_charge

    sync_membership_payment_state_for_charge(
        charge=charge,
        actor=instance.recorded_by if kwargs.get("signal") is post_save else None,
    )


@receiver(pre_save, sender=Payment)
def remember_payment_status(sender, instance: Payment, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    instance._previous_status = Payment.objects.filter(pk=instance.pk).values_list("status", flat=True).first()


@receiver(post_save, sender=Payment)
def create_payment_notification(sender, instance: Payment, created: bool, **kwargs):
    if not instance.membership_id:
        return
    member_id = instance.membership.member_id
    association_name = instance.membership.association.name
    amount = format_ugx(instance.amount_paid)
    charge_label = ""
    if instance.charge_id:
        charge_label = instance.charge.title or instance.charge.get_purpose_display()

    if created and instance.status == "recorded":
        notify_member_on_commit(
            member_id=member_id,
            title="Payment Recorded",
            message=(
                f"A cash payment of {amount} has been recorded against your "
                f"{association_name} {charge_label or 'charge'}."
            ),
            notification_type="payment",
            related_url=f"/payments/{instance.pk}",
            related_object_type="payment",
            related_object_id=instance.pk,
            deduplication_key=f"payment_{instance.pk}_recorded",
        )
        return

    old_status = getattr(instance, "_previous_status", None)
    if old_status != "reversed" and instance.status == "reversed":
        notify_member_on_commit(
            member_id=member_id,
            title="Payment Reversed",
            message=(
                f"A payment record of {amount} was reversed and no longer counts "
                "toward your paid balance."
            ),
            notification_type="payment",
            related_url=f"/payments/{instance.pk}",
            related_object_type="payment",
            related_object_id=instance.pk,
            deduplication_key=f"payment_{instance.pk}_reversed",
        )


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
    if instance.status != "active":
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


@receiver(post_save, sender=Event)
def create_event_notifications(sender, instance: Event, created: bool, **kwargs):
    if not created:
        return
    member_ids = (
        Membership.objects.filter(association_id=instance.association_id, status="active", member__user__isnull=False)
        .values_list("member_id", flat=True)
        .distinct()
    )
    notify_members_on_commit(
        member_ids=member_ids,
        title="New Event",
        message=f"{instance.association.name} has added a new event: {instance.title}.",
        notification_type="event",
        related_url=f"/events/{instance.pk}",
        related_object_type="event",
        related_object_id=instance.pk,
        deduplication_key=f"event_{instance.pk}_published",
        preference_key=PREFERENCE_EVENTS,
    )


@receiver(pre_save, sender=Announcement)
def remember_announcement_published(sender, instance: Announcement, **kwargs):
    if not instance.pk:
        instance._previous_is_published = None
        return
    instance._previous_is_published = (
        Announcement.objects.filter(pk=instance.pk).values_list("is_published", flat=True).first()
    )


@receiver(post_save, sender=Announcement)
def create_announcement_notifications(sender, instance: Announcement, created: bool, **kwargs):
    old_published = getattr(instance, "_previous_is_published", None)
    became_published = instance.is_published and (created or old_published is False)
    if not became_published:
        return

    members = Member.objects.filter(user__isnull=False, user__is_active=True)
    if instance.audience == "association":
        members = members.filter(memberships__association_id=instance.association_id, memberships__status="active")
    elif instance.audience == "faculty":
        members = members.filter(Q(faculty_id=instance.faculty_id) | Q(course__faculty_id=instance.faculty_id))
    elif instance.audience == "guild":
        members = members.filter(guild_executive_roles__isnull=False)

    association_name = f"{instance.association.name} " if instance.association_id else ""
    notify_members_on_commit(
        member_ids=members.values_list("id", flat=True).distinct(),
        title="New Announcement",
        message=f"{association_name}published a new announcement: {instance.title}.",
        notification_type="announcement",
        related_url=f"/announcements/{instance.pk}",
        related_object_type="announcement",
        related_object_id=instance.pk,
        deduplication_key=f"announcement_{instance.pk}_published",
        preference_key=PREFERENCE_ANNOUNCEMENTS,
    )

@receiver([post_save, post_delete], sender=Payment)
def update_bill_membership_status(sender, instance: Payment, **kwargs):
    """Auto-update BillMembership status when payment recorded/updated/deleted"""
    charge_id = instance.charge_id
    if not charge_id:
        return
    from campus_nexus.models import Charge

    charge = Charge.objects.filter(pk=charge_id).select_related("bill_membership").first()
    if charge and charge.bill_membership:
        bill_mem = charge.bill_membership
        bill_mem.update_status_from_payments()
