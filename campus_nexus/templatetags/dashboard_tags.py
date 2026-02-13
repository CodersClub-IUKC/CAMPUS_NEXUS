import json
from django import template
from django.db.models import Count, Sum
from campus_nexus.models import Association, Member, Membership, Payment, Event

register = template.Library()

def _json_list(x):
    return json.dumps(list(x))

@register.simple_tag(takes_context=True)
def dean_dashboard_data(context):
    total_associations = Association.objects.count()

    # TOTAL members in system (unique)
    total_members = Member.objects.count() or 0

    total_payments = Payment.objects.count()
    total_amount = Payment.objects.aggregate(total=Sum("amount_paid"))["total"] or 0

    # Members by association (distinct members per association)
    members_qs = (
        Membership.objects.values("association__name")
        .annotate(total=Count("member_id", distinct=True))
        .order_by("-total")
    )

    # Take top N for charts
    top_members_qs = list(members_qs[:12])

    members_labels = [r["association__name"] for r in top_members_qs]
    members_data = [int(r["total"]) for r in top_members_qs]

    # Percent share per association (based on TOTAL members in system)
    members_percent = []
    for r in top_members_qs:
        if total_members == 0:
            members_percent.append(0.0)
        else:
            members_percent.append(round((int(r["total"]) / total_members) * 100, 2))

    # Top association by members (+ percent)
    if top_members_qs:
        top_assoc_name = top_members_qs[0]["association__name"]
        top_assoc_members = int(top_members_qs[0]["total"])
        top_assoc_percent = 0.0 if total_members == 0 else round((top_assoc_members / total_members) * 100, 2)
    else:
        top_assoc_name = ""
        top_assoc_members = 0
        top_assoc_percent = 0.0

    # Payments by association (through membership)
    payments_qs = (
        Payment.objects.values("membership__association__name")
        .annotate(total=Sum("amount_paid"))
        .order_by("-total")[:10]
    )
    pay_labels = [r["membership__association__name"] for r in payments_qs]
    pay_data = [float(r["total"] or 0) for r in payments_qs]

    # Events by association
    events_qs = (
        Event.objects.values("association__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:12]
    )
    ev_labels = [r["association__name"] for r in events_qs]
    ev_data = [int(r["total"]) for r in events_qs]
    
    # Member type distribution (based on TOTAL members)
    member_type_qs = (
        Member.objects.values("member_type")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    type_labels = [r["member_type"].title() for r in member_type_qs]
    type_data = [int(r["total"]) for r in member_type_qs]

    type_percent = []
    for v in type_data:
        if total_members == 0:
            type_percent.append(0.0)
        else:
            type_percent.append(round((v / total_members) * 100, 2))

    return {
        "total_associations": total_associations,
        "total_members": total_members,
        "total_payments": total_payments,
        "total_amount_collected": total_amount,

        # Top association summary
        "top_assoc_name": top_assoc_name,
        "top_assoc_members": top_assoc_members,
        "top_assoc_percent": top_assoc_percent,

        "members_by_association": {
            "labels": _json_list(members_labels),
            "data": _json_list(members_data),
            "percent": _json_list(members_percent), 
        },
        "payments_by_association": {
            "labels": _json_list(pay_labels),
            "data": _json_list(pay_data),
        },
        "events_by_association": {
            "labels": _json_list(ev_labels),
            "data": _json_list(ev_data),
        },
        
        "member_type_distribution": {
            "labels": _json_list(type_labels),
            "data": _json_list(type_data),
            "percent": _json_list(type_percent),
        },
    }
