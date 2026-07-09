import hashlib
import logging

from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from campus_nexus.services.audit import record_audit_event

logger = logging.getLogger(__name__)

GENERIC_PASSWORD_RESET_DETAIL = (
    "If an eligible Campus Nexus account matches the information provided, "
    "password recovery instructions will be sent."
)


def normalize_member_login_identifier(identifier):
    return str(identifier or "").strip()


def get_eligible_member_portal_user(identifier):
    normalized = normalize_member_login_identifier(identifier)
    if not normalized:
        return None

    User = get_user_model()
    username_field = User.USERNAME_FIELD
    try:
        user = User.objects.select_related("member_profile").get(**{username_field: normalized})
    except User.DoesNotExist:
        return None
    except User.MultipleObjectsReturned:
        logger.warning("Multiple users matched member password reset identifier field %s", username_field)
        return None

    if not user.is_active:
        return None
    if not hasattr(user, "member_profile"):
        return None
    return user


def make_password_reset_url(user):
    origin = getattr(settings, "MEMBER_PORTAL_ORIGIN", "").rstrip("/")
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{origin}/reset-password/{uid}/{token}", uid, token


def decode_uid(uid):
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
        return None

    User = get_user_model()
    try:
        return User.objects.select_related("member_profile").get(pk=user_id)
    except (User.DoesNotExist, ValueError):
        return None


def token_is_valid_for_member_portal_user(uid, token):
    user = decode_uid(uid)
    if user is None or not user.is_active or not hasattr(user, "member_profile"):
        return False, None
    return default_token_generator.check_token(user, token), user


def identifier_send_allowed(identifier):
    limit = int(getattr(settings, "PASSWORD_RESET_IDENTIFIER_MAX_REQUESTS_PER_WINDOW", 3))
    timeout = int(getattr(settings, "PASSWORD_RESET_IDENTIFIER_WINDOW_SECONDS", 3600))
    if limit <= 0:
        return True

    normalized = normalize_member_login_identifier(identifier).lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    cache_key = f"member-password-reset:identifier:{digest}"
    try:
        count = cache.add(cache_key, 1, timeout=timeout)
        if count:
            return True
        return cache.incr(cache_key) <= limit
    except ValueError:
        cache.set(cache_key, 1, timeout=timeout)
        return True


def send_member_password_reset_email(user, request=None):
    reset_url, _uid, _token = make_password_reset_url(user)
    member = user.member_profile
    context = {
        "user": user,
        "member": member,
        "reset_url": reset_url,
        "site_name": "Campus Nexus",
        "request": request,
    }
    subject = "".join(
        render_to_string("campus_nexus/email/password_reset_subject.txt", context).splitlines()
    )
    text_body = render_to_string("campus_nexus/email/password_reset_email.txt", context)
    html_body = render_to_string("campus_nexus/email/password_reset_email.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[user.email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def request_member_password_reset(identifier, request=None):
    user = get_eligible_member_portal_user(identifier)
    if user is None:
        return False

    member = user.member_profile
    record_audit_event(
        actor=None,
        action="MEMBER_PASSWORD_RESET_REQUESTED",
        obj=member,
    )

    if not user.email:
        logger.warning("Eligible member password reset user has no email address", extra={"user_id": user.pk})
        return True

    if not identifier_send_allowed(identifier):
        logger.warning("Member password reset email suppressed by identifier rate limit", extra={"user_id": user.pk})
        return True

    try:
        send_member_password_reset_email(user, request=request)
    except Exception:
        logger.exception("Member password reset email delivery failed", extra={"user_id": user.pk})
        return True

    return True


def blacklist_user_refresh_tokens(user):
    try:
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
    except Exception:
        return 0

    blacklisted_count = 0
    for outstanding_token in OutstandingToken.objects.filter(user=user):
        _blacklisted, created = BlacklistedToken.objects.get_or_create(token=outstanding_token)
        if created:
            blacklisted_count += 1
    return blacklisted_count


def invalidate_user_sessions(user):
    deleted_count = 0
    for session in Session.objects.all():
        data = session.get_decoded()
        if str(data.get("_auth_user_id")) == str(user.pk):
            session.delete()
            deleted_count += 1
    return deleted_count


def confirm_member_password_reset(uid, token, new_password):
    valid, user = token_is_valid_for_member_portal_user(uid, token)
    if not valid:
        return False, {"token": ["Invalid or expired password reset token."]}

    try:
        password_validation.validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        return False, {"new_password": list(exc.messages)}

    member = user.member_profile
    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password"])
        refresh_tokens_blacklisted = blacklist_user_refresh_tokens(user)
        sessions_invalidated = invalidate_user_sessions(user)
        record_audit_event(
            actor=None,
            action="MEMBER_PASSWORD_RESET_COMPLETED",
            obj=member,
            metadata={
                "refresh_tokens_blacklisted": refresh_tokens_blacklisted,
                "sessions_invalidated": sessions_invalidated,
            },
        )

    return True, None
