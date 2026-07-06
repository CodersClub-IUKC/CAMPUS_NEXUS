import json
from decimal import Decimal
from datetime import date

from dateutil.relativedelta import relativedelta
from django import template
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from campus_nexus.models import (
    Announcement,
    Association,
    AuditLog,
    Charge,
    Expense,
    Event,
    Member,
    Membership,
    Payment,
)

register = template.Library()

ZERO = Decimal("0.00")


def _json_list(x):
    return json.dumps(list(x))


def _monthly_trend(association, months=6):
    """Returns last `months` months of income and expenses as chart-ready lists."""
    today = timezone.localdate()
    labels, income_data, expense_data = [], [], []

    for i in range(months - 1, -1, -1):
        anchor = today - relativedelta(months=i)
        label = anchor.strftime("%b %Y")
        labels.append(label)

        inc = (
            Payment.objects.filter(
                membership__association=association,
                status="recorded",
                paid_at__year=anchor.year,
                paid_at__month=anchor.month,
            ).aggregate(s=Sum("amount_paid"))["s"] or ZERO
        )
        exp = (
            Expense.objects.filter(
                association=association,
                status="recorded",
                spent_at__year=anchor.year,
                spent_at__month=anchor.month,
            ).aggregate(s=Sum("amount"))["s"] or ZERO
        )
        income_data.append(float(inc))
        expense_data.append(float(exp))

    return {
        "labels": _json_list(labels),
        "income": _json_list(income_data),
        "expenses": _json_list(expense_data),
    }


def _system_monthly_finance(months=6):
    """Returns last `months` months of recorded income and expenses."""
    today = timezone.localdate()
    labels, income_data, expense_data = [], [], []

    for i in range(months - 1, -1, -1):
        anchor = today - relativedelta(months=i)
        labels.append(anchor.strftime("%b %Y"))

        income = (
            Payment.objects.filter(
                status="recorded",
                paid_at__year=anchor.year,
                paid_at__month=anchor.month,
            ).aggregate(total=Sum("amount_paid")).get("total") or ZERO
        )
        expense = (
            Expense.objects.filter(
                status="recorded",
                spent_at__year=anchor.year,
                spent_at__month=anchor.month,
            ).aggregate(total=Sum("amount")).get("total") or ZERO
        )
        income_data.append(float(income))
        expense_data.append(float(expense))

    return {
        "labels": _json_list(labels),
        "income": _json_list(income_data),
        "expenses": _json_list(expense_data),
    }


def _system_membership_growth(months=6):
    today = timezone.localdate()
    labels, members_data, memberships_data = [], [], []

    for i in range(months - 1, -1, -1):
        anchor = today - relativedelta(months=i)
        labels.append(anchor.strftime("%b %Y"))
        members_data.append(
            Member.objects.filter(
                created_at__year=anchor.year,
                created_at__month=anchor.month,
            ).count()
        )
        memberships_data.append(
            Membership.objects.filter(
                status="active",
                joined_at__year=anchor.year,
                joined_at__month=anchor.month,
            ).count()
        )

    return {
        "labels": _json_list(labels),
        "members": _json_list(members_data),
        "memberships": _json_list(memberships_data),
    }


def _outstanding_balance(charges_qs):
    """Compute outstanding balance at the DB level — no Python iteration."""
    result = (
        charges_qs.filter(status__in=["unpaid", "partial"])
        .annotate(
            paid_total=Coalesce(
                Sum("payments__amount_paid", filter=Q(payments__status="recorded")),
                ZERO,
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .annotate(
            remaining=ExpressionWrapper(
                F("amount_due") - F("paid_total"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .filter(remaining__gt=0)
        .aggregate(total=Sum("remaining"))
    )
    return result["total"] or ZERO


@register.simple_tag(takes_context=True)
def dean_dashboard_data(context):
    total_associations = Association.objects.count()
    total_members = Member.objects.count() or 0

    faculty_based = Association.objects.filter(faculty__isnull=False).count()
    non_faculty_based = Association.objects.filter(faculty__isnull=True).count()

    active_memberships = Membership.objects.filter(status="active").count()
    inactive_memberships = Membership.objects.filter(status="inactive").count()
    suspended_memberships = Membership.objects.filter(status="suspended").count()
    active_percent = (
        round((active_memberships / total_members) * 100, 1)
        if total_members else 0.0
    )

    charges_qs = Charge.objects.exclude(status="cancelled")
    total_billed = charges_qs.aggregate(total=Sum("amount_due")).get("total") or ZERO
    total_collected = (
        Payment.objects.filter(status="recorded")
        .aggregate(total=Sum("amount_paid"))
        .get("total") or ZERO
    )
    total_expenses = (
        Expense.objects.filter(status="recorded")
        .aggregate(total=Sum("amount"))
        .get("total") or ZERO
    )
    outstanding_balance = _outstanding_balance(charges_qs)
    overdue_count = charges_qs.filter(is_overdue=True, status__in=["unpaid", "partial"]).count()
    open_charges_count = charges_qs.filter(status__in=["unpaid", "partial"]).count()
    collection_rate = (
        round((float(total_collected) / float(total_billed)) * 100, 1)
        if total_billed > 0 else 0.0
    )

    members_qs = (
        Membership.objects.values("association__name")
        .annotate(total=Count("member_id", distinct=True))
        .order_by("-total")
    )
    top_members_qs = list(members_qs[:12])

    members_labels = [r["association__name"] for r in top_members_qs]
    members_data = [int(r["total"]) for r in top_members_qs]

    members_percent = [
        0.0 if total_members == 0 else round((v / total_members) * 100, 2)
        for v in members_data
    ]

    if top_members_qs:
        top_assoc_name = top_members_qs[0]["association__name"]
        top_assoc_members = int(top_members_qs[0]["total"])
        top_assoc_percent = (
            0.0 if total_members == 0
            else round((top_assoc_members / total_members) * 100, 2)
        )
    else:
        top_assoc_name = ""
        top_assoc_members = 0
        top_assoc_percent = 0.0

    events_qs = (
        Event.objects.values("association__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:12]
    )
    ev_labels = [r["association__name"] for r in events_qs]
    ev_data = [int(r["total"]) for r in events_qs]
    total_events = Event.objects.count()
    upcoming_events = (
        Event.objects.filter(event_date__gte=timezone.now())
        .select_related("association")
        .order_by("event_date")[:5]
    )
    recent_events = (
        Event.objects.select_related("association")
        .order_by("-event_date")[:5]
    )

    member_type_qs = (
        Member.objects.values("member_type")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    type_labels = [r["member_type"].title() for r in member_type_qs]
    type_data = [int(r["total"]) for r in member_type_qs]
    member_type_rows = [
        {
            "label": label,
            "total": total,
            "percent": 0.0 if total_members == 0 else round((total / total_members) * 100, 1),
        }
        for label, total in zip(type_labels, type_data)
    ]
    type_percent = [row["percent"] for row in member_type_rows]

    latest_announcements = (
        Announcement.objects.filter(is_published=True)
        .select_related("association", "faculty", "posted_by")
        .order_by("-created_at")[:5]
    )
    total_published_announcements = Announcement.objects.filter(is_published=True).count()
    recent_audit = (
        AuditLog.objects.select_related("actor", "association")
        .order_by("-created_at")[:5]
    )
    top_finance_rows = list(
        Payment.objects.filter(status="recorded")
        .values("membership__association__name")
        .annotate(total=Sum("amount_paid"))
        .order_by("-total")[:5]
    )
    risk_rows = list(
        charges_qs.filter(is_overdue=True, status__in=["unpaid", "partial"])
        .values("association__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:5]
    )

    return {
        "total_associations": total_associations,
        "total_members": total_members,
        "total_events": total_events,
        "faculty_based_associations": faculty_based,
        "non_faculty_based_associations": non_faculty_based,
        "membership_status": {
            "active": active_memberships,
            "inactive": inactive_memberships,
            "suspended": suspended_memberships,
            "active_percent": active_percent,
        },
        "finance": {
            "total_billed": total_billed,
            "total_collected": total_collected,
            "total_expenses": total_expenses,
            "net_position": total_collected - total_expenses,
            "outstanding_balance": outstanding_balance,
            "overdue_charges_count": overdue_count,
            "open_charges_count": open_charges_count,
            "collection_rate": collection_rate,
        },
        "top_assoc_name": top_assoc_name,
        "top_assoc_members": top_assoc_members,
        "top_assoc_percent": top_assoc_percent,
        "membership_growth": _system_membership_growth(months=6),
        "monthly_finance": _system_monthly_finance(months=6),
        "members_by_association": {
            "labels": _json_list(members_labels),
            "data": _json_list(members_data),
            "percent": _json_list(members_percent),
            "rows": top_members_qs[:5],
        },
        "events_by_association": {
            "labels": _json_list(ev_labels),
            "data": _json_list(ev_data),
        },
        "member_type_distribution": {
            "labels": _json_list(type_labels),
            "data": _json_list(type_data),
            "percent": _json_list(type_percent),
            "rows": member_type_rows,
        },
        "assoc_type_split": {
            "labels": _json_list(["Faculty-based", "Non faculty-based"]),
            "data": _json_list([faculty_based, non_faculty_based]),
        },
        "announcements": {
            "latest": latest_announcements,
            "published_count": total_published_announcements,
        },
        "events": {
            "upcoming": upcoming_events,
            "recent": recent_events,
        },
        "top_finance_rows": top_finance_rows,
        "risk_rows": risk_rows,
        "recent_audit": recent_audit,
    }


@register.simple_tag(takes_context=True)
def guild_dashboard_data(context):
    total_associations = Association.objects.count()
    total_members = Member.objects.count() or 0
    total_memberships = Membership.objects.filter(status="active").count()

    top_assoc_qs = (
        Membership.objects.filter(status="active")
        .values("association__name")
        .annotate(total=Count("member_id", distinct=True))
        .order_by("-total")[:6]
    )
    top_assoc_labels = [r["association__name"] for r in top_assoc_qs]
    top_assoc_data = [int(r["total"]) for r in top_assoc_qs]

    member_type_qs = (
        Member.objects.values("member_type")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    type_labels = [r["member_type"].title() for r in member_type_qs]
    type_data = [int(r["total"]) for r in member_type_qs]

    latest_announcements = (
        Announcement.objects.all()
        .select_related("association", "faculty", "posted_by")
        .order_by("-created_at")[:6]
    )
    drafts = Announcement.objects.filter(is_published=False).count()
    published = Announcement.objects.filter(is_published=True).count()

    return {
        "total_associations": total_associations,
        "total_members": total_members,
        "active_memberships": total_memberships,
        "top_associations": {
            "labels": _json_list(top_assoc_labels),
            "data": _json_list(top_assoc_data),
        },
        "member_type_distribution": {
            "labels": _json_list(type_labels),
            "data": _json_list(type_data),
        },
        "announcements": {
            "latest": latest_announcements,
            "drafts": drafts,
            "published": published,
        },
    }


@register.simple_tag(takes_context=True)
def association_dashboard_data(context):
    request = context.get("request")
    assoc_admin = getattr(getattr(request, "user", None), "association_admin", None)
    if not assoc_admin:
        return {}

    assoc = assoc_admin.association

    membership_status_qs = (
        Membership.objects.filter(association=assoc)
        .values("status")
        .annotate(total=Count("id"))
    )
    membership_counts = {row["status"]: row["total"] for row in membership_status_qs}
    total_members = sum(membership_counts.values())
    active_members = membership_counts.get("active", 0)

    total_events = Event.objects.filter(association=assoc).count()
    charges_qs = Charge.objects.filter(association=assoc).exclude(status="cancelled")

    total_billed = charges_qs.aggregate(total=Sum("amount_due")).get("total") or ZERO

    total_collected = (
        Payment.objects.filter(membership__association=assoc, status="recorded")
        .aggregate(total=Sum("amount_paid"))
        .get("total") or ZERO
    )
    total_expenses = (
        Expense.objects.filter(association=assoc, status="recorded")
        .aggregate(total=Sum("amount"))
        .get("total") or ZERO
    )

    outstanding_balance = _outstanding_balance(charges_qs)

    overdue_charges_count = charges_qs.filter(
        is_overdue=True, status__in=["unpaid", "partial"]
    ).count()
    open_charges_count = charges_qs.filter(status__in=["unpaid", "partial"]).count()
    paid_charges_count = charges_qs.filter(status="paid").count()
    partial_charges_count = charges_qs.filter(status="partial").count()
    unpaid_charges_count = charges_qs.filter(status="unpaid").count()

    collection_rate = (
        round((float(total_collected) / float(total_billed)) * 100, 1)
        if total_billed > 0 else 0.0
    )

    today = timezone.localdate()
    this_month_collected = (
        Payment.objects.filter(
            membership__association=assoc,
            status="recorded",
            paid_at__year=today.year,
            paid_at__month=today.month,
        ).aggregate(total=Sum("amount_paid")).get("total") or ZERO
    )
    this_month_expenses = (
        Expense.objects.filter(
            association=assoc,
            status="recorded",
            spent_at__year=today.year,
            spent_at__month=today.month,
        ).aggregate(total=Sum("amount")).get("total") or ZERO
    )

    net_position = total_collected - total_expenses
    net_margin_percent = (
        round((net_position / total_collected) * Decimal("100.00"), 2)
        if total_collected > 0 else ZERO
    )

    recent_payments = (
        Payment.objects.filter(membership__association=assoc, status="recorded")
        .select_related("membership__member", "charge")
        .order_by("-recorded_at")[:6]
    )
    recent_expenses = (
        Expense.objects.filter(association=assoc, status="recorded")
        .select_related("recorded_by")
        .order_by("-spent_at", "-recorded_at")[:5]
    )
    open_charges = (
        charges_qs.filter(status__in=["unpaid", "partial"])
        .select_related("membership__member")
        .order_by("-is_overdue", "due_date", "-created_at")[:5]
    )
    upcoming_events = (
        Event.objects.filter(association=assoc, event_date__gte=timezone.now())
        .order_by("event_date")[:5]
    )

    latest_announcements = (
        Announcement.objects.filter(
            Q(is_published=True, audience="all")
            | Q(is_published=True, audience="association", association=assoc)
            | Q(posted_by=request.user)
        )
        .select_related("association", "faculty", "posted_by")
        .order_by("-created_at")[:6]
    )

    monthly_trend = _monthly_trend(assoc, months=6)

    return {
        "association_name": assoc.name,
        "total_members": total_members,
        "active_members": active_members,
        "total_events": total_events,
        "membership_status": membership_counts,
        "finance": {
            "total_billed": total_billed,
            "total_collected": total_collected,
            "total_expenses": total_expenses,
            "net_position": net_position,
            "net_margin_percent": net_margin_percent,
            "outstanding_balance": outstanding_balance,
            "overdue_charges_count": overdue_charges_count,
            "open_charges_count": open_charges_count,
            "paid_charges_count": paid_charges_count,
            "partial_charges_count": partial_charges_count,
            "unpaid_charges_count": unpaid_charges_count,
            "this_month_collected": this_month_collected,
            "this_month_expenses": this_month_expenses,
            "collection_rate": collection_rate,
        },
        "monthly_trend": monthly_trend,
        "recent_payments": recent_payments,
        "recent_expenses": recent_expenses,
        "open_charges": open_charges,
        "upcoming_events": upcoming_events,
        "announcements": {"latest": latest_announcements},
    }


@register.simple_tag
def superuser_dashboard_data():
    total_members = Member.objects.count()
    total_associations = Association.objects.count()
    total_memberships = Membership.objects.filter(status="active").count()
    total_events = Event.objects.count()

    total_collected = (
        Payment.objects.filter(status="recorded")
        .aggregate(s=Sum("amount_paid"))["s"] or ZERO
    )
    total_expenses = (
        Expense.objects.filter(status="recorded")
        .aggregate(s=Sum("amount"))["s"] or ZERO
    )
    overdue_count = Charge.objects.filter(
        is_overdue=True, status__in=["unpaid", "partial"]
    ).count()
    this_month = timezone.localdate()
    members_this_month = Member.objects.filter(
        created_at__year=this_month.year,
        created_at__month=this_month.month,
    ).count()
    payments_this_month = (
        Payment.objects.filter(
            status="recorded",
            paid_at__year=this_month.year,
            paid_at__month=this_month.month,
        ).aggregate(total=Sum("amount_paid")).get("total") or ZERO
    )
    expenses_this_month = (
        Expense.objects.filter(
            status="recorded",
            spent_at__year=this_month.year,
            spent_at__month=this_month.month,
        ).aggregate(total=Sum("amount")).get("total") or ZERO
    )

    member_type_qs = (
        Member.objects.values("member_type")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    type_labels = [r["member_type"].title() for r in member_type_qs]
    type_data = [int(r["total"]) for r in member_type_qs]

    top_assoc_qs = (
        Membership.objects.filter(status="active")
        .values("association__name")
        .annotate(total=Count("member_id", distinct=True))
        .order_by("-total")[:8]
    )
    top_labels = [r["association__name"] for r in top_assoc_qs]
    top_data = [int(r["total"]) for r in top_assoc_qs]

    charge_status_qs = (
        Charge.objects.exclude(status="cancelled")
        .values("status")
        .annotate(total=Count("id"))
    )
    charge_status = {row["status"]: row["total"] for row in charge_status_qs}
    charge_status_labels = ["Paid", "Partial", "Unpaid", "Overdue"]
    charge_status_data = [
        int(charge_status.get("paid", 0)),
        int(charge_status.get("partial", 0)),
        int(charge_status.get("unpaid", 0)),
        int(overdue_count),
    ]

    recent_payments = (
        Payment.objects.filter(status="recorded")
        .select_related("membership__member", "membership__association", "charge")
        .order_by("-recorded_at")[:5]
    )
    recent_expenses = (
        Expense.objects.filter(status="recorded")
        .select_related("association", "recorded_by")
        .order_by("-spent_at", "-recorded_at")[:5]
    )
    upcoming_events = (
        Event.objects.filter(event_date__gte=timezone.now())
        .select_related("association")
        .order_by("event_date")[:5]
    )
    recent_audit = (
        AuditLog.objects.select_related("actor", "association")
        .order_by("-created_at")[:6]
    )
    top_association_rows = list(
        Membership.objects.filter(status="active")
        .values("association__name")
        .annotate(total=Count("member_id", distinct=True))
        .order_by("-total")[:5]
    )

    return {
        "total_members": total_members,
        "total_associations": total_associations,
        "active_memberships": total_memberships,
        "total_events": total_events,
        "total_collected": total_collected,
        "total_expenses": total_expenses,
        "overdue_count": overdue_count,
        "members_this_month": members_this_month,
        "payments_this_month": payments_this_month,
        "expenses_this_month": expenses_this_month,
        "net_position": total_collected - total_expenses,
        "monthly_finance": _system_monthly_finance(months=6),
        "membership_growth": _system_membership_growth(months=6),
        "charge_status": {
            "paid": charge_status.get("paid", 0),
            "partial": charge_status.get("partial", 0),
            "unpaid": charge_status.get("unpaid", 0),
            "overdue": overdue_count,
            "labels": _json_list(charge_status_labels),
            "data": _json_list(charge_status_data),
        },
        "member_type_distribution": {
            "labels": _json_list(type_labels),
            "data": _json_list(type_data),
        },
        "top_associations": {
            "labels": _json_list(top_labels),
            "data": _json_list(top_data),
        },
        "top_association_rows": top_association_rows,
        "recent_payments": recent_payments,
        "recent_expenses": recent_expenses,
        "upcoming_events": upcoming_events,
        "recent_audit": recent_audit,
    }
