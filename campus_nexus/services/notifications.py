from __future__ import annotations

from decimal import Decimal
import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from campus_nexus.models import Member, Notification
from campus_nexus.services.notification_preferences import is_optional_notification_enabled


logger = logging.getLogger(__name__)


def format_ugx(amount: Decimal) -> str:
    value = amount or Decimal("0.00")
    return f"UGX {value:,.0f}"


def create_member_notification(
    *,
    member: Member,
    title: str,
    message: str,
    notification_type: str,
    related_url: str = "",
    related_object_type: str = "",
    related_object_id: str | int = "",
    deduplication_key: str | None = None,
    preference_key: str | None = None,
):
    if not member or not member.user_id:
        return None
    user = member.user
    if not user.is_active:
        return None
    if not is_optional_notification_enabled(member, preference_key):
        return None

    if deduplication_key:
        existing = Notification.objects.filter(
            recipient=user,
            deduplication_key=deduplication_key,
        ).first()
        if existing:
            return existing

    notification = Notification(
        recipient=user,
        title=title,
        message=message,
        notification_type=notification_type,
        related_url=related_url or "",
        related_object_type=related_object_type or "",
        related_object_id=str(related_object_id or ""),
        deduplication_key=deduplication_key or None,
    )
    notification.full_clean()

    try:
        notification.save()
        return notification
    except IntegrityError:
        if not deduplication_key:
            raise
        return Notification.objects.filter(
            recipient=user,
            deduplication_key=deduplication_key,
        ).first()


def notify_member_on_commit(*, member_id: int, **kwargs):
    def _create():
        try:
            member = Member.objects.select_related("user").filter(pk=member_id).first()
            if member is None:
                return
            create_member_notification(member=member, **kwargs)
        except Exception:
            logger.exception("Failed to create member notification")

    transaction.on_commit(_create)


def notify_members_on_commit(*, member_ids, **kwargs):
    member_ids = tuple(dict.fromkeys(member_ids))

    def _create_many():
        for member in Member.objects.select_related("user", "notification_preferences").filter(pk__in=member_ids):
            try:
                create_member_notification(member=member, **kwargs)
            except (IntegrityError, ValidationError):
                logger.exception("Failed to create member notification for member %s", member.pk)

    transaction.on_commit(_create_many)
