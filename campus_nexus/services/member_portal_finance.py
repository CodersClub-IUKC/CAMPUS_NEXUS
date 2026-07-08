from __future__ import annotations

from decimal import Decimal

from django.db.models import Q, Sum

from campus_nexus.models import Charge, Membership, Payment


ZERO = Decimal("0.00")


def decimal_string(value) -> str:
    value = value or ZERO
    return f"{value:.2f}"


def total_recorded_payments(memberships):
    return (
        Payment.objects.filter(membership__in=memberships, status="recorded")
        .aggregate(total=Sum("amount_paid"))
        .get("total")
        or ZERO
    )


def outstanding_balance(memberships):
    charges = (
        Charge.objects.filter(membership__in=memberships)
        .exclude(status="cancelled")
        .annotate(
            paid_total=Sum(
                "payments__amount_paid",
                filter=Q(payments__status="recorded"),
            )
        )
        .only("amount_due")
    )

    total = ZERO
    for charge in charges:
        remaining = charge.amount_due - (charge.paid_total or ZERO)
        if remaining > 0:
            total += remaining
    return total


def membership_financial_summary(membership: Membership):
    memberships = Membership.objects.filter(pk=membership.pk)
    return {
        "total_paid": decimal_string(total_recorded_payments(memberships)),
        "outstanding_balance": decimal_string(outstanding_balance(memberships)),
    }

