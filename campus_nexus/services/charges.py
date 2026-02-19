from __future__ import annotations

from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from campus_nexus.models import Charge, Fee, Membership
from campus_nexus.services.subscriptions import ensure_current_subscription_charge


@transaction.atomic
def get_or_create_charge_for_fee(*, membership: Membership, fee: Fee, user) -> Charge:
    """
    For subscription fees:
      - Return the current cycle charge (create if missing)

    For membership fees:
      - Create/reuse a single charge (no cycle needed)
    """
    if fee.fee_type == "subscription":
        ch = ensure_current_subscription_charge(membership)
        # ensure_current_subscription_charge returns None if no sub fee configured,
        # but here we have fee, so it should not be None.
        if ch:
            return ch

    # membership fee or any non-sub fee:
    # (you may still want period bounds, but simplest is one charge per membership+fee)
    charge, _ = Charge.objects.get_or_create(
        membership=membership,
        association_id=membership.association_id,
        fee=fee,
        purpose="membership_fee" if fee.fee_type == "membership" else "other",
        period_start=None,
        period_end=None,
        defaults={
            "title": f"{fee.get_fee_type_display()}",
            "amount_due": fee.amount,
            "due_date": timezone.localdate() + timedelta(days=int(fee.grace_days or 0)),
            "created_by": user,
            "status": "unpaid",
        },
    )
    charge.recompute_status()
    charge.save(update_fields=["status"])
    return charge


@transaction.atomic
def create_charge_custom(
    *,
    membership: Membership,
    purpose: str,
    title: str,
    amount_due,
    due_date,
    description: str,
    user,
):
    charge = Charge.objects.create(
        membership=membership,
        association_id=membership.association_id,
        fee=None,
        purpose=purpose or "other",
        title=title or "",
        description=description or "",
        amount_due=amount_due,
        due_date=due_date,
        created_by=user,
        status="unpaid",
    )
    charge.recompute_status()
    charge.save(update_fields=["status"])
    return charge
