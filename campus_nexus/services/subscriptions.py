from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

from campus_nexus.models import Fee, Charge, Membership


def get_subscription_fee(association_id: int) -> Fee | None:
    return (
        Fee.objects.filter(association_id=association_id, fee_type="subscription")
        .order_by("-created_at")
        .first()
    )


def cycle_bounds(anchor: date, duration_months: int, today: date) -> tuple[date, date]:
    """
    Returns the current cycle [start, end] given an anchor date and cycle duration.
    end is inclusive for display, but you can treat it as inclusive consistently.
    """
    if duration_months <= 0:
        # fallback: treat as yearly if misconfigured
        duration_months = 12

    start = anchor
    while True:
        end = start + relativedelta(months=duration_months) - timedelta(days=1)
        if today <= end:
            return start, end
        start = start + relativedelta(months=duration_months)


@transaction.atomic
def ensure_current_subscription_charge(membership: Membership) -> Charge | None:
    """
    Ensures the membership has a subscription charge for the *current* cycle.
    Returns the charge or None if the association has no subscription fee.
    """
    fee = get_subscription_fee(membership.association_id)
    if not fee:
        return None

    anchor = membership.subscription_anchor_date or timezone.localdate()
    if not membership.subscription_anchor_date:
        membership.subscription_anchor_date = anchor
        membership.save(update_fields=["subscription_anchor_date"])

    today = timezone.localdate()
    period_start, period_end = cycle_bounds(anchor, fee.duration_months, today)

    # due date = period_end (+ grace days if due end is prefferred)
    due_date = period_end
    if fee.grace_days:
        due_date = due_date + timedelta(days=int(fee.grace_days))

    charge, created = Charge.objects.get_or_create(
        membership=membership,
        association_id=membership.association_id,
        fee=fee,
        period_start=period_start,
        period_end=period_end,
        defaults={
            "purpose": "subscription_fee",
            "title": f"Subscription ({period_start} → {period_end})",
            "amount_due": fee.amount,
            "due_date": due_date,
            "status": "unpaid",
        },
    )

    # keep overdue flag fresh
    charge.is_overdue = bool(charge.due_date and charge.balance > 0 and today > charge.due_date)
    charge.recompute_status()
    charge.save(update_fields=["status", "is_overdue"])

    return charge


def recompute_overdue_flags_for_association(association_id: int) -> None:
    today = timezone.localdate()
    qs = Charge.objects.filter(association_id=association_id, purpose="subscription_fee").select_related("fee")
    for c in qs:
        grace = int(c.fee.grace_days) if c.fee_id else 0
        due = c.due_date + timedelta(days=grace) if c.due_date and grace else c.due_date
        c.is_overdue = bool(due and c.balance > 0 and today > due)
        c.recompute_status()
        c.save(update_fields=["status", "is_overdue"])
