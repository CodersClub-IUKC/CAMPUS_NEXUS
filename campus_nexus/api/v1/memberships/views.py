from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from campus_nexus.api.v1.memberships.serializers import (
    MembershipCardSerializer,
    PublicMembershipVerificationSerializer,
)
from campus_nexus.api.v1.permissions import IsAuthenticatedMember
from campus_nexus.api.v1.serializers import MembershipSerializer
from campus_nexus.models import Membership


class MembershipListView(generics.ListAPIView):
    serializer_class = MembershipSerializer
    permission_classes = (IsAuthenticatedMember,)

    def get_queryset(self):
        return (
            Membership.objects.filter(member=self.request.user.member_profile)
            .select_related("association", "association__faculty")
            .order_by("association__name")
        )


class MembershipDetailView(generics.RetrieveAPIView):
    serializer_class = MembershipSerializer
    permission_classes = (IsAuthenticatedMember,)
    lookup_url_kwarg = "identifier"

    def get_queryset(self):
        return (
            Membership.objects.filter(member=self.request.user.member_profile)
            .select_related("association", "association__faculty")
        )


class MembershipCardView(generics.RetrieveAPIView):
    serializer_class = MembershipCardSerializer
    permission_classes = (IsAuthenticatedMember,)
    lookup_url_kwarg = "identifier"

    def get_queryset(self):
        return (
            Membership.objects.filter(member=self.request.user.member_profile)
            .select_related("member", "association", "association__faculty")
        )


class PublicMembershipVerificationView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request, token):
        membership = (
            Membership.objects.filter(verification_token=token)
            .select_related("member", "association")
            .first()
        )
        if membership is None:
            return Response(
                {
                    "valid": False,
                    "verification_status": "not_found",
                    "verification_status_display": "Membership Verification Not Found",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(PublicMembershipVerificationSerializer(membership, context={"request": request}).data)
