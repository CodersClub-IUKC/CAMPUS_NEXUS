from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from campus_nexus.api.v1.pagination import MemberPortalPagination
from campus_nexus.api.v1.permissions import IsAuthenticatedMember
from campus_nexus.api.v1.serializers import (
    MembershipApplicationCreateSerializer,
    MembershipApplicationSerializer,
)
from campus_nexus.models import MembershipApplication
from campus_nexus.services.membership_application import (
    MembershipApplicationError,
    cancel_membership_application,
    create_membership_application,
)


def application_error_response(exc: MembershipApplicationError, *, status_code=status.HTTP_400_BAD_REQUEST):
    return Response(
        {
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
        status=status_code,
    )


class MembershipApplicationListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticatedMember,)
    pagination_class = MemberPortalPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return MembershipApplicationCreateSerializer
        return MembershipApplicationSerializer

    def get_queryset(self):
        return (
            MembershipApplication.objects.filter(member=self.request.user.member_profile)
            .select_related("association", "association__faculty", "charge")
            .order_by("-applied_at")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            application = create_membership_application(
                member=request.user.member_profile,
                association=serializer.validated_data["association"],
            )
        except MembershipApplicationError as exc:
            return application_error_response(exc)

        output = MembershipApplicationSerializer(application, context={"request": request})
        return Response(output.data, status=status.HTTP_201_CREATED)


class MembershipApplicationDetailView(generics.RetrieveAPIView):
    serializer_class = MembershipApplicationSerializer
    permission_classes = (IsAuthenticatedMember,)
    lookup_url_kwarg = "identifier"

    def get_queryset(self):
        return MembershipApplication.objects.filter(member=self.request.user.member_profile).select_related(
            "association",
            "association__faculty",
            "charge",
        )


class MembershipApplicationCancelView(APIView):
    permission_classes = (IsAuthenticatedMember,)

    def post(self, request, identifier):
        try:
            application = MembershipApplication.objects.get(
                pk=identifier,
                member=request.user.member_profile,
            )
            application = cancel_membership_application(
                application=application,
                member=request.user.member_profile,
            )
        except MembershipApplication.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except MembershipApplicationError as exc:
            return application_error_response(exc)

        serializer = MembershipApplicationSerializer(application, context={"request": request})
        return Response(serializer.data)

