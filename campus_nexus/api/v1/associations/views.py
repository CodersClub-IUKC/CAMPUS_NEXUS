from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from rest_framework import generics

from campus_nexus.api.v1.pagination import MemberPortalPagination
from campus_nexus.api.v1.permissions import IsAuthenticatedMember
from campus_nexus.api.v1.serializers import AssociationSerializer
from campus_nexus.models import Association, Fee, Membership, MembershipApplication
from campus_nexus.services.membership_eligibility import member_academic_faculty_id


class AssociationQuerysetMixin:
    serializer_class = AssociationSerializer
    permission_classes = (IsAuthenticatedMember,)
    pagination_class = MemberPortalPagination
    lookup_url_kwarg = "identifier"

    def get_queryset(self):
        member = self.request.user.member_profile
        faculty_id = member_academic_faculty_id(member)
        discoverable_filter = Q(faculty__isnull=True)
        if faculty_id:
            discoverable_filter |= Q(faculty_id=faculty_id)

        return (
            Association.objects.filter(discoverable_filter)
            .select_related("faculty")
            .annotate(
                member_count=Count("memberships", distinct=True),
                upcoming_event_count=Count(
                    "events",
                    filter=Q(events__event_date__gte=timezone.now()),
                    distinct=True,
                ),
            )
            .prefetch_related(
                Prefetch(
                    "fees",
                    queryset=Fee.objects.filter(fee_type="membership").order_by("-created_at"),
                    to_attr="prefetched_fees",
                )
            )
            .order_by("name")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        member = self.request.user.member_profile
        context["membership_statuses"] = dict(
            Membership.objects.filter(member=member).values_list("association_id", "status")
        )
        context["applications"] = {
            application.association_id: application
            for application in MembershipApplication.objects.filter(member=member)
            .exclude(status__in=[
                MembershipApplication.STATUS_REJECTED,
                MembershipApplication.STATUS_CANCELLED,
            ])
            .select_related("association")
            .order_by("-applied_at")
        }
        return context


class AssociationListView(AssociationQuerysetMixin, generics.ListAPIView):
    pass


class AssociationDetailView(AssociationQuerysetMixin, generics.RetrieveAPIView):
    pass
