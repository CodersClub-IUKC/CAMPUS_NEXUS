from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q, Sum

from campus_nexus.models import Charge, Payment
from campus_nexus.services.member_portal_finance import decimal_string


ZERO = Decimal("0.00")


def get_member_charge_queryset(member):
    return (
        Charge.objects.filter(membership__member=member)
        .select_related(
            "association",
            "association__faculty",
            "membership",
            "membership__member",
            "fee",
            "membership_application",
        )
        .annotate(
            recorded_paid_total=Sum(
                "payments__amount_paid",
                filter=Q(payments__status="recorded"),
            )
        )
        .order_by("-created_at", "-id")
    )


def get_member_payment_queryset(member):
    return (
        Payment.objects.filter(membership__member=member)
        .select_related(
            "membership",
            "membership__member",
            "membership__association",
            "membership__association__faculty",
            "charge",
            "charge__fee",
            "charge__membership_application",
            "fee",
        )
        .order_by("-paid_at", "-recorded_at", "-id")
    )


def charge_recorded_paid(charge) -> Decimal:
    annotated = getattr(charge, "recorded_paid_total", None)
    if annotated is not None:
        return annotated or ZERO
    return (
        charge.payments.filter(status="recorded")
        .aggregate(total=Sum("amount_paid"))
        .get("total")
        or ZERO
    )


def charge_recorded_balance(charge) -> Decimal:
    remaining = charge.amount_due - charge_recorded_paid(charge)
    return remaining if remaining > ZERO else ZERO


def get_member_finance_summary(member):
    charges = get_member_charge_queryset(member).exclude(status="cancelled")

    charge_totals = Charge.objects.filter(membership__member=member).exclude(status="cancelled").aggregate(
        total_billed=Sum("amount_due"),
        total_charges=Count("id"),
        paid_charges=Count("id", filter=Q(status="paid")),
        partial_charges=Count("id", filter=Q(status="partial")),
        unpaid_charges=Count("id", filter=Q(status="unpaid")),
        overdue_charges=Count("id", filter=Q(is_overdue=True)),
    )
    payment_totals = Payment.objects.filter(
        membership__member=member,
        status="recorded",
        charge__isnull=False,
    ).exclude(charge__status="cancelled").aggregate(total_paid=Sum("amount_paid"))

    total_billed = charge_totals["total_billed"] or ZERO
    total_paid = payment_totals["total_paid"] or ZERO
    outstanding = ZERO
    membership_fee_obligations = []

    for charge in charges:
        balance = charge_recorded_balance(charge)
        outstanding += balance
        if charge.purpose == "membership_fee":
            membership_fee_obligations.append(
                {
                    "id": charge.pk,
                    "association": {
                        "id": charge.association_id,
                        "name": charge.association.name,
                    },
                    "amount": decimal_string(charge.amount_due),
                    "paid_amount": decimal_string(charge_recorded_paid(charge)),
                    "balance": decimal_string(balance),
                    "status": charge.status,
                    "due_date": charge.due_date,
                }
            )

    if total_billed > ZERO:
        percentage = (total_paid / total_billed * Decimal("100")).quantize(Decimal("0.01"))
    else:
        percentage = ZERO

    recent_payments = [
        {
            "id": payment.pk,
            "amount": decimal_string(payment.amount_paid),
            "paid_at": payment.paid_at,
            "payment_method": payment.payment_method,
            "status": payment.status,
            "association": {
                "id": payment.membership.association_id,
                "name": payment.membership.association.name,
            },
            "charge_id": payment.charge_id,
        }
        for payment in get_member_payment_queryset(member).filter(status="recorded")[:5]
    ]

    return {
        "total_billed": decimal_string(total_billed),
        "total_paid": decimal_string(total_paid),
        "outstanding_balance": decimal_string(outstanding),
        "payment_completion_percentage": decimal_string(percentage),
        "charge_counts": {
            "total": charge_totals["total_charges"] or 0,
            "paid": charge_totals["paid_charges"] or 0,
            "partial": charge_totals["partial_charges"] or 0,
            "unpaid": charge_totals["unpaid_charges"] or 0,
            "overdue": charge_totals["overdue_charges"] or 0,
        },
        "membership_fee_obligations": membership_fee_obligations,
        "recent_payments": recent_payments,
    }
