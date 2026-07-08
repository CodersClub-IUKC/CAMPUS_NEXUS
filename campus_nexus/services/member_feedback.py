from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from campus_nexus.models import Association, Feedback, Member, Membership
from campus_nexus.services.audit import record_audit_event
from campus_nexus.services.notifications import notify_member_on_commit


@dataclass(frozen=True)
class MemberFeedbackError(Exception):
    code: str
    message: str


def validate_feedback_association(member: Member, association: Association | None):
    if association is None:
        return
    if not Membership.objects.filter(member=member, association=association).exists():
        raise MemberFeedbackError(
            "feedback_association_not_allowed",
            "Feedback can only be related to associations connected to your memberships.",
        )


def create_member_feedback(*, member: Member, data: dict) -> Feedback:
    association = data.get("association")
    validate_feedback_association(member, association)
    with transaction.atomic():
        feedback = Feedback(
            member=member,
            submitted_by=member.user if member.user_id else None,
            association=association,
            category=data.get("category") or Feedback.CATEGORY_GENERAL,
            subject=data.get("subject", ""),
            message=data.get("message", ""),
        )
        feedback.full_clean()
        feedback.save()
        record_audit_event(
            actor=feedback.submitted_by,
            action="MEMBER_FEEDBACK_SUBMITTED",
            obj=feedback,
            association=feedback.association,
            metadata={
                "feedback_id": str(feedback.pk),
                "member_id": str(member.pk),
                "association_id": str(feedback.association_id or ""),
                "status": feedback.status,
                "category": feedback.category,
            },
        )
        notify_member_on_commit(
            member_id=member.pk,
            title="Feedback Submitted",
            message="Your feedback has been received and is now open.",
            notification_type="system",
            related_url=f"/feedback/{feedback.pk}",
            related_object_type="feedback",
            related_object_id=feedback.pk,
            deduplication_key=f"feedback_{feedback.pk}_submitted",
        )
        return feedback


def apply_admin_feedback_update(*, feedback: Feedback, actor, old_status: str, old_response: str):
    response_changed = (feedback.admin_response or "") != (old_response or "")
    status_changed = feedback.status != old_status
    if response_changed and feedback.admin_response:
        feedback.responded_by = actor
        feedback.responded_at = timezone.now()

    update_fields = ["status", "admin_response", "updated_at"]
    if response_changed and feedback.admin_response:
        update_fields.extend(["responded_by", "responded_at"])
    feedback.full_clean()
    feedback.save(update_fields=update_fields)

    if status_changed:
        record_audit_event(
            actor=actor,
            action="MEMBER_FEEDBACK_STATUS_CHANGED",
            obj=feedback,
            association=feedback.association,
            metadata={
                "feedback_id": str(feedback.pk),
                "member_id": str(feedback.member_id or ""),
                "association_id": str(feedback.association_id or ""),
                "old_status": old_status,
                "new_status": feedback.status,
            },
        )
    if response_changed:
        record_audit_event(
            actor=actor,
            action="MEMBER_FEEDBACK_RESPONDED",
            obj=feedback,
            association=feedback.association,
            metadata={
                "feedback_id": str(feedback.pk),
                "member_id": str(feedback.member_id or ""),
                "association_id": str(feedback.association_id or ""),
                "status": feedback.status,
            },
        )
    if (status_changed or response_changed) and feedback.member_id:
        notify_member_on_commit(
            member_id=feedback.member_id,
            title="Feedback Updated",
            message=f'Your feedback "{feedback.subject}" has been updated.',
            notification_type="system",
            related_url=f"/feedback/{feedback.pk}",
            related_object_type="feedback",
            related_object_id=feedback.pk,
            deduplication_key=f"feedback_{feedback.pk}_updated_{feedback.updated_at.timestamp()}",
        )
