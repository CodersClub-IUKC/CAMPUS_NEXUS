from django.db.models import Count, Q
from django.utils import timezone

from campus_nexus.api.v1.serializers import (
    AnnouncementSerializer,
    EventSerializer,
    MembershipApplicationSerializer,
)
from campus_nexus.models import Announcement, Event, Membership, MembershipApplication
from campus_nexus.services.member_finance import get_member_finance_summary


def build_member_dashboard(member, request):
    memberships = Membership.objects.filter(member=member).select_related("association")
    association_ids = list(memberships.values_list("association_id", flat=True))

    membership_status = {
        row["status"]: row["count"]
        for row in memberships.values("status").annotate(count=Count("id"))
    }
    applications = MembershipApplication.objects.filter(member=member).select_related("association", "charge")
    application_status = {
        row["status"]: row["count"]
        for row in applications.values("status").annotate(count=Count("id"))
    }
    finance_summary = get_member_finance_summary(member)

    upcoming_events = (
        Event.objects.filter(association_id__in=association_ids, event_date__gte=timezone.now())
        .select_related("association")
        .order_by("event_date")[:5]
    )

    latest_announcements = (
        Announcement.objects.filter(is_published=True)
        .filter(
            Q(audience="all")
            | Q(audience="guild")
            | Q(audience="association", association_id__in=association_ids)
            | Q(audience="faculty", faculty_id=member.faculty_id)
        )
        .select_related("association", "faculty")
        .order_by("-created_at")[:5]
    )

    return {
        "member": {
            "first_name": member.first_name,
            "last_name": member.last_name,
            "full_name": member.full_name,
            "registration_number": member.registration_number,
        },
        "summary": {
            "membership_count": memberships.count(),
            "active_memberships": membership_status.get("active", 0),
            "total_paid": finance_summary["total_paid"],
            "outstanding_balance": finance_summary["outstanding_balance"],
        },
        "membership_status": membership_status,
        "membership_applications": {
            "pending_approval": application_status.get(MembershipApplication.STATUS_PENDING_APPROVAL, 0),
            "pending_payment": application_status.get(MembershipApplication.STATUS_APPROVED_PENDING_PAYMENT, 0),
            "rejected": application_status.get(MembershipApplication.STATUS_REJECTED, 0),
        },
        "recent_membership_applications": MembershipApplicationSerializer(
            applications.order_by("-applied_at")[:5],
            many=True,
            context={"request": request},
        ).data,
        "recent_payments": [],
        "upcoming_events": EventSerializer(upcoming_events, many=True, context={"request": request}).data,
        "latest_announcements": AnnouncementSerializer(
            latest_announcements,
            many=True,
            context={"request": request},
        ).data,
    }
