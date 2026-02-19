from django.conf import settings
from django.core.mail import send_mail


def send_subscription_reminder_email(*, member, association, charge, days_left: int):
    if not member.email:
        return False

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "Campus Nexus <no-reply@campusnexus.local>")

    subject = f"Subscription reminder: {association.name}"
    message = (
        f"Hello {member.first_name},\n\n"
        f"This is a reminder that your subscription for '{association.name}' is due.\n\n"
        f"Amount due: {charge.amount_due}\n"
        f"Amount paid: {charge.amount_paid_total}\n"
        f"Balance: {charge.balance}\n"
        f"Due date: {charge.due_date}\n"
        f"Days left: {days_left}\n\n"
        f"Thank you,\nCampus Nexus"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=[member.email],
        fail_silently=True,
    )
    return True
