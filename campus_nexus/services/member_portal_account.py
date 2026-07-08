from __future__ import annotations

import re
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import transaction

from campus_nexus.models import Member
from campus_nexus.services.audit import record_audit_event
from campus_nexus.services.notifications import notify_member_on_commit
from campus_nexus.services.onboarding import send_onboarding_invitation_email


@dataclass(frozen=True)
class MemberPortalAccountError(Exception):
    code: str
    message: str


@dataclass(frozen=True)
class MemberPortalActivationResult:
    user: object
    email_sent: bool
    email_error: str | None = None


def _normalise_username_part(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", ".", value)
    value = re.sub(r"[._-]{2,}", ".", value).strip("._-")
    return value


def generate_member_portal_username(member: Member) -> str:
    User = get_user_model()
    candidates = []

    if member.first_name or member.last_name:
        candidates.append(_normalise_username_part(f"{member.first_name}.{member.last_name}"))
    if member.email:
        candidates.append(_normalise_username_part(member.email.split("@", 1)[0]))
    if member.registration_number:
        candidates.append(_normalise_username_part(member.registration_number))

    base = next((candidate for candidate in candidates if candidate), "member")
    username = base[:140]
    counter = 2
    while User.objects.filter(username=username).exists():
        suffix = str(counter)
        username = f"{base[:150 - len(suffix)]}{suffix}"
        counter += 1
    return username


def _user_has_admin_role(user) -> bool:
    return any(
        (
            user.is_staff,
            user.is_superuser,
            hasattr(user, "association_admin"),
            hasattr(user, "guild"),
            hasattr(user, "dean"),
        )
    )


def _validate_activation(member: Member):
    if member.user_id:
        raise MemberPortalAccountError(
            "portal_account_already_exists",
            "A portal account already exists for this member.",
        )
    if not member.email:
        raise MemberPortalAccountError(
            "member_email_required",
            "Member email is required before activating a portal account.",
        )

    User = get_user_model()
    existing_user = User.objects.filter(email__iexact=member.email).first()
    if existing_user:
        linked_member = getattr(existing_user, "member_profile", None)
        if linked_member and linked_member.pk == member.pk:
            raise MemberPortalAccountError(
                "portal_account_already_exists",
                "A portal account already exists for this member.",
            )
        if linked_member:
            raise MemberPortalAccountError(
                "user_linked_to_another_member",
                "This user is already linked to another member.",
            )
        if _user_has_admin_role(existing_user):
            raise MemberPortalAccountError(
                "admin_role_account_conflict",
                "This email belongs to an administrative account and cannot be linked automatically.",
            )
        raise MemberPortalAccountError(
            "email_account_conflict",
            "This email belongs to another user account and cannot be linked automatically.",
        )


def activate_member_portal_account(*, member: Member, activated_by):
    with transaction.atomic():
        member = Member.objects.select_for_update().get(pk=member.pk)
        _validate_activation(member)

        User = get_user_model()
        user = User(
            username=generate_member_portal_username(member),
            email=member.email,
            first_name=member.first_name,
            last_name=member.last_name,
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        user.set_unusable_password()
        user.full_clean()
        user.save()

        member.user = user
        member.save(update_fields=["user"])

        record_audit_event(
            actor=activated_by,
            action="MEMBER_PORTAL_ACCOUNT_ACTIVATED",
            obj=member,
            metadata={
                "member_id": str(member.pk),
                "user_id": str(user.pk),
                "username": user.username,
            },
        )
        notify_member_on_commit(
            member_id=member.pk,
            title="Welcome to Campus Nexus",
            message=(
                "Your Member Portal account is active. You can now manage your memberships, "
                "applications, finances, events and announcements."
            ),
            notification_type="account",
            related_url="/dashboard",
            related_object_type="member",
            related_object_id=member.pk,
            deduplication_key=f"member_{member.pk}_portal_welcome",
        )

    member.refresh_from_db()
    try:
        email_sent = send_member_portal_setup_email(member=member, sent_by=activated_by)
    except Exception as exc:
        return MemberPortalActivationResult(user=user, email_sent=False, email_error=str(exc))
    return MemberPortalActivationResult(user=user, email_sent=email_sent)


def send_member_portal_setup_email(*, member: Member, sent_by):
    if not member.user_id:
        raise MemberPortalAccountError(
            "portal_account_not_activated",
            "This member does not have a portal account yet.",
        )
    user = member.user
    sent = send_onboarding_invitation_email(
        user=user,
        invited_by=sent_by.get_full_name() or sent_by.get_username(),
    )
    record_audit_event(
        actor=sent_by,
        action="MEMBER_PORTAL_SETUP_LINK_SENT",
        obj=member,
        metadata={
            "member_id": str(member.pk),
            "user_id": str(user.pk),
            "username": user.username,
            "email_sent": bool(sent),
        },
    )
    return sent


@transaction.atomic
def disable_member_portal_account(*, member: Member, disabled_by):
    member = Member.objects.select_for_update().select_related("user").get(pk=member.pk)
    if not member.user_id:
        raise MemberPortalAccountError(
            "portal_account_not_activated",
            "This member does not have a portal account yet.",
        )
    user = member.user
    user.is_active = False
    user.save(update_fields=["is_active"])
    record_audit_event(
        actor=disabled_by,
        action="MEMBER_PORTAL_ACCOUNT_DISABLED",
        obj=member,
        metadata={"member_id": str(member.pk), "user_id": str(user.pk), "username": user.username},
    )
    return user


@transaction.atomic
def enable_member_portal_account(*, member: Member, enabled_by):
    member = Member.objects.select_for_update().select_related("user").get(pk=member.pk)
    if not member.user_id:
        raise MemberPortalAccountError(
            "portal_account_not_activated",
            "This member does not have a portal account yet.",
        )
    user = member.user
    user.is_active = True
    user.save(update_fields=["is_active"])
    record_audit_event(
        actor=enabled_by,
        action="MEMBER_PORTAL_ACCOUNT_ENABLED",
        obj=member,
        metadata={"member_id": str(member.pk), "user_id": str(user.pk), "username": user.username},
    )
    return user
