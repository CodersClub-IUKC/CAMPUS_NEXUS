from django.db.models import Q
from rest_framework import generics

from campus_nexus.api.v1.pagination import MemberPortalPagination
from campus_nexus.api.v1.permissions import IsAuthenticatedMember
from campus_nexus.api.v1.serializers import AnnouncementSerializer
from campus_nexus.models import Announcement


class AnnouncementQuerysetMixin:
    serializer_class = AnnouncementSerializer
    permission_classes = (IsAuthenticatedMember,)
    pagination_class = MemberPortalPagination
    lookup_url_kwarg = "identifier"

    def get_queryset(self):
        member = self.request.user.member_profile
        association_ids = member.memberships.values_list("association_id", flat=True)
        return (
            Announcement.objects.filter(is_published=True)
            .filter(
                Q(audience="all")
                | Q(audience="guild")
                | Q(audience="association", association_id__in=association_ids)
                | Q(audience="faculty", faculty_id=member.faculty_id)
            )
            .select_related("association", "association__faculty", "faculty")
            .order_by("-created_at")
        )


class AnnouncementListView(AnnouncementQuerysetMixin, generics.ListAPIView):
    pass


class AnnouncementDetailView(AnnouncementQuerysetMixin, generics.RetrieveAPIView):
    pass

