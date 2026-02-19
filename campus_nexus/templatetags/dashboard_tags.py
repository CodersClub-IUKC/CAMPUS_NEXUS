import json
from django import template
from django.db.models import Count
from django.db.models import Q
from campus_nexus.models import Association, Member, Membership, Event, Announcement

register = template.Library()


def _json_list(x):
    return json.dumps(list(x))


@register.simple_tag(takes_context=True)
def dean_dashboard_data(context):
    total_associations = Association.objects.count()
    total_members = Member.objects.count() or 0

    faculty_based = Association.objects.filter(faculty__isnull=False).count()
    non_faculty_based = Association.objects.filter(faculty__isnull=True).count()

    # Members by association (distinct members per association)
    members_qs = (
        Membership.objects.values("association__name")
        .annotate(total=Count("member_id", distinct=True))
        .order_by("-total")
    )
    top_members_qs = list(members_qs[:12])

    members_labels = [r["association__name"] for r in top_members_qs]
    members_data = [int(r["total"]) for r in top_members_qs]

    members_percent = []
    for v in members_data:
        members_percent.append(0.0 if total_members == 0 else round((v / total_members) * 100, 2))

    if top_members_qs:
        top_assoc_name = top_members_qs[0]["association__name"]
        top_assoc_members = int(top_members_qs[0]["total"])
        top_assoc_percent = 0.0 if total_members == 0 else round((top_assoc_members / total_members) * 100, 2)
    else:
        top_assoc_name = ""
        top_assoc_members = 0
        top_assoc_percent = 0.0

    # Events by association
    events_qs = (
        Event.objects.values("association__name")
        .annotate(total=Count("id"))
        .order_by("-total")[:12]
    )
    ev_labels = [r["association__name"] for r in events_qs]
    ev_data = [int(r["total"]) for r in events_qs]

    # Member type distribution
    member_type_qs = (
        Member.objects.values("member_type")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    type_labels = [r["member_type"].title() for r in member_type_qs]
    type_data = [int(r["total"]) for r in member_type_qs]
    type_percent = [0.0 if total_members == 0 else round((v / total_members) * 100, 2) for v in type_data]

    # Announcements (Dean should see published only)
    latest_announcements = (
        Announcement.objects.filter(is_published=True)
        .select_related("association", "faculty", "posted_by")
        .order_by("-created_at")[:5]
    )
    total_published_announcements = Announcement.objects.filter(is_published=True).count()

    return {
        "total_associations": total_associations,
        "total_members": total_members,

        "faculty_based_associations": faculty_based,
        "non_faculty_based_associations": non_faculty_based,

        "top_assoc_name": top_assoc_name,
        "top_assoc_members": top_assoc_members,
        "top_assoc_percent": top_assoc_percent,

        "members_by_association": {
            "labels": _json_list(members_labels),
            "data": _json_list(members_data),
            "percent": _json_list(members_percent),
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
        "assoc_type_split": {
            "labels": _json_list(["Faculty-based", "Non faculty-based"]),
            "data": _json_list([faculty_based, non_faculty_based]),
        },
        "announcements": {
            "latest": latest_announcements,
            "published_count": total_published_announcements,
        },
    }


@register.simple_tag(takes_context=True)
def guild_dashboard_data(context):
    total_associations = Association.objects.count()
    total_members = Member.objects.count() or 0

    # Guild can see all announcements (published + drafts)
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

    total_members = (
        Membership.objects.filter(association=assoc).values("member_id").distinct().count()
    )
    total_events = Event.objects.filter(association=assoc).count()

    # Assoc admin sees:
    # - published global
    # - published targeted to their association
    # - plus their own drafts (posted_by=user)
    latest_announcements = (
        Announcement.objects.filter(
            Q(is_published=True, audience="all")
            | Q(is_published=True, audience="association", association=assoc)
            | Q(posted_by=request.user)
        )
        .select_related("association", "faculty", "posted_by")
        .order_by("-created_at")[:6]
    )

    return {
        "association_name": assoc.name,
        "total_members": total_members,
        "total_events": total_events,
        "announcements": {"latest": latest_announcements},
    }
