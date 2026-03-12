from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def build_password_setup_link(*, user, base_url=None):
    root_url = (base_url or getattr(settings, "CAMPUS_NEXUS_SITE_URL", "")).strip()
    if not root_url:
        root_url = "http://localhost:8000"
    root_url = root_url.rstrip("/") + "/"

    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    path = reverse("password_reset_confirm", kwargs={"uidb64": uidb64, "token": token})
    return urljoin(root_url, path.lstrip("/"))


def send_onboarding_invitation_email(*, user, invited_by=None, base_url=None):
    if not getattr(user, "email", ""):
        return False

    setup_link = build_password_setup_link(user=user, base_url=base_url)
    display_name = user.get_full_name() or user.get_username()

    inviter_line = ""
    if invited_by:
        inviter_line = f"\nInvited by: {invited_by}\n"

    subject = "Set up your Campus Nexus account"
    message = (
        f"Hello {display_name},\n\n"
        "An account has been created for you on Campus Nexus.\n"
        f"{inviter_line}"
        "Use the secure link below to set your password and activate access:\n"
        f"{setup_link}\n\n"
        "This link can only be used once and expires automatically.\n"
        "If you were not expecting this invitation, ignore this message.\n\n"
        "Campus Nexus"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=False,
    )
    return True
