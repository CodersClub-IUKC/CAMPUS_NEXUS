from rest_framework import generics, status
from rest_framework.response import Response

from campus_nexus.api.v1.feedback.serializers import MemberFeedbackCreateSerializer, MemberFeedbackSerializer
from campus_nexus.api.v1.pagination import MemberPortalPagination
from campus_nexus.api.v1.permissions import IsAuthenticatedMember
from campus_nexus.models import Feedback
from campus_nexus.services.member_feedback import MemberFeedbackError, create_member_feedback


def feedback_error_response(exc: MemberFeedbackError):
    return Response(
        {
            "detail": exc.message,
            "code": exc.code,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


class MemberFeedbackListCreateView(generics.ListCreateAPIView):
    permission_classes = (IsAuthenticatedMember,)
    pagination_class = MemberPortalPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return MemberFeedbackCreateSerializer
        return MemberFeedbackSerializer

    def get_queryset(self):
        queryset = (
            Feedback.objects.filter(member=self.request.user.member_profile)
            .select_related("association", "association__faculty", "responded_by")
            .order_by("-submitted_at", "-id")
        )
        status_value = self.request.query_params.get("status")
        if status_value:
            valid_statuses = {choice[0] for choice in Feedback.STATUS_CHOICES}
            queryset = queryset.filter(status=status_value) if status_value in valid_statuses else queryset.none()
        category = self.request.query_params.get("category")
        if category:
            valid_categories = {choice[0] for choice in Feedback.CATEGORY_CHOICES}
            queryset = queryset.filter(category=category) if category in valid_categories else queryset.none()
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            feedback = create_member_feedback(
                member=request.user.member_profile,
                data=serializer.validated_data,
            )
        except MemberFeedbackError as exc:
            return feedback_error_response(exc)
        output = MemberFeedbackSerializer(feedback, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


class MemberFeedbackDetailView(generics.RetrieveAPIView):
    serializer_class = MemberFeedbackSerializer
    permission_classes = (IsAuthenticatedMember,)
    lookup_url_kwarg = "identifier"

    def get_queryset(self):
        return (
            Feedback.objects.filter(member=self.request.user.member_profile)
            .select_related("association", "association__faculty", "responded_by")
        )
