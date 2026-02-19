from datetime import date
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from dateutil.relativedelta import relativedelta

from .models import Charge, Fee, Membership


def get_or_create_charge_for_fee(*, membership: Membership, fee: Fee, user=None) -> Charge:
    """
    For dues (membership/subscription), reuse an existing open charge for this membership+fee+period,
    otherwise create a new one.
    """
    today = timezone.localdate()

    # Compute a period window (optional but useful)
    period_start = today
    period_end = today + relativedelta(months=fee.duration_months or 0) if fee.duration_months else None

    # Reuse an existing open charge for same membership+fee that is not cancelled/paid
    existing = (
        Charge.objects.filter(
            membership=membership,
            fee=fee,
            status__in=["unpaid", "partial"],
        )
        .order_by("-created_at")
        .first()
    )
    if existing:
        return existing

    purpose = "membership_fee" if fee.fee_type == "membership" else "subscription_fee"
    title = dict(Fee.FEE_TYPE_CHOICES).get(fee.fee_type, "Fee")

    return Charge.objects.create(
        association=membership.association,
        membership=membership,
        fee=fee,
        purpose=purpose,
        title=title,
        description="",
        amount_due=fee.amount,
        due_date=today,  # you can make this smarter later
        created_by=user,
        period_start=period_start,
        period_end=period_end,
    )


def create_charge_custom(
    *,
    membership: Membership,
    purpose: str,
    title: str,
    amount_due: Decimal,
    due_date=None,
    description: str = "",
    user=None,
) -> Charge:
    if amount_due is None or amount_due <= 0:
        raise ValidationError({"amount_due": "Amount due must be greater than 0."})

    return Charge.objects.create(
        association=membership.association,
        membership=membership,
        fee=None,
        purpose=purpose or "other",
        title=title or "",
        description=description or "",
        amount_due=amount_due,
        due_date=due_date,
        created_by=user,
    )
