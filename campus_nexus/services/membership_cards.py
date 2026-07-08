from __future__ import annotations

import uuid

from django.db import transaction

from campus_nexus.models import Membership
from campus_nexus.services.audit import record_audit_event


def membership_card_available(membership: Membership) -> bool:
    return membership.status == "active"


def membership_verification_path(membership: Membership) -> str:
    return f"/verify/membership/{membership.verification_token}"


def mask_registration_number(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if "-" in value:
        parts = value.split("-")
        if len(parts) >= 3:
            middle = "-".join(parts[1:-1])
            return f"{parts[0]}-{'*' * max(5, len(middle))}-{parts[-1]}"
    if len(value) <= 4:
        return "*" * len(value)
    if len(value) <= 8:
        return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
    return f"{value[:3]}{'*' * (len(value) - 6)}{value[-3:]}"


def rotate_membership_verification_token(*, membership: Membership, actor) -> Membership:
    with transaction.atomic():
        membership = Membership.objects.select_for_update().get(pk=membership.pk)
        old_token = str(membership.verification_token)
        membership.verification_token = uuid.uuid4()
        new_token = str(membership.verification_token)
        membership.save(update_fields=["verification_token"])
        record_audit_event(
            actor=actor,
            action="MEMBERSHIP_VERIFICATION_TOKEN_ROTATED",
            obj=membership,
            association=membership.association,
            metadata={
                "old_token_suffix": old_token[-8:],
                "new_token_suffix": new_token[-8:],
                "membership_id": str(membership.pk),
            },
        )
        return membership
