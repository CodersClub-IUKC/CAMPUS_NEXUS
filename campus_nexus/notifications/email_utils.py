import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_payment_recorded_email(*, member, association, payment, charge):
    """
    Sends a payment confirmation email to the member.
    Errors are logged but never raised — email delivery must never crash the admin page.
    """
    to_email = member.email
    if not to_email:
        return

    subject = f"Payment received - {association.name}"

    purpose = getattr(charge, "title", "") or getattr(charge, "purpose", "Payment")
    bal = getattr(charge, "balance", None)

    message = (
        f"Hello {member.full_name},\n\n"
        f"Your payment has been recorded in Campus Nexus.\n\n"
        f"Association: {association.name}\n"
        f"Purpose: {purpose}\n"
        f"Amount Paid: {payment.amount_paid}\n"
        f"Payment Method: {payment.get_payment_method_display() if hasattr(payment, 'get_payment_method_display') else payment.payment_method}\n"
        f"Reference: {payment.reference_code or 'N/A'}\n"
        f"Paid At: {payment.paid_at}\n\n"
    )

    if bal is not None:
        message += f"Remaining Balance: {bal}\n\n"

    message += "Thank you.\nCampus Nexus"

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or settings.EMAIL_HOST_USER,
            recipient_list=[to_email],
            fail_silently=False,
        )
    except Exception as exc:
        # Log the error so it appears in server logs but never propagate it —
        # a broken SMTP config must never prevent a treasurer from recording a payment.
        logger.exception(
            "Payment confirmation email failed for member %s (payment #%s): %s",
            member.pk,
            payment.pk,
            exc,
        )
