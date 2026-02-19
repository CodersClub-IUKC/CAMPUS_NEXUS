from django.conf import settings
from django.core.mail import send_mail


def send_membership_assigned_email(*, member, association, membership):
    subject = f"You've joined {association.name} on Campus Nexus"
    message = (
        f"Hello {member.full_name},\n\n"
        f"You have been added as a member of {association.name} on Campus Nexus.\n\n"
        f"Status: {membership.get_status_display() if hasattr(membership, 'get_status_display') else membership.status}\n"
        f"Joined on: {membership.joined_at:%Y-%m-%d %H:%M}\n\n"
        "If you believe this was a mistake, please contact your association admin.\n\n"
        "Regards,\nCampus Nexus"
    )

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@campusnexus.local"

    # safety: only send if member has email
    if not member.email:
        return

    send_mail(
        subject,
        message,
        from_email,
        [member.email],
        fail_silently=False,
    )


def send_membership_removed_email(*, member, association):
    subject = f"Removed from {association.name} on Campus Nexus"
    message = (
        f"Hello {member.full_name},\n\n"
        f"You have been removed from {association.name} on Campus Nexus.\n\n"
        "If you believe this was a mistake, please contact your association admin.\n\n"
        "Regards,\nCampus Nexus"
    )

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@campusnexus.local"

    if not member.email:
        return

    send_mail(
        subject,
        message,
        from_email,
        [member.email],
        fail_silently=False,
    )
