from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from campus_nexus.api.v1.events.serializers import EventRegistrationSerializer
from campus_nexus.api.v1.pagination import MemberPortalPagination
from campus_nexus.api.v1.permissions import IsAuthenticatedMember
from campus_nexus.api.v1.serializers import EventSerializer
from campus_nexus.models import Event, EventRegistration, Membership
from campus_nexus.services.event_registration import (
    EventRegistrationError,
    cancel_event_registration,
    register_for_event,
)


def event_registration_error_response(exc: EventRegistrationError, *, status_code=status.HTTP_400_BAD_REQUEST):
    return Response(
        {
            "detail": exc.message,
            "code": exc.code,
        },
        status=status_code,
    )


class EventQuerysetMixin:
    serializer_class = EventSerializer
    permission_classes = (IsAuthenticatedMember,)
    pagination_class = MemberPortalPagination
    lookup_url_kwarg = "identifier"

    def get_queryset(self):
        association_ids = self.request.user.member_profile.memberships.values_list("association_id", flat=True)
        return (
            Event.objects.filter(association_id__in=association_ids, event_date__gte=timezone.now())
            .select_related("association", "association__faculty")
            .annotate(
                registered_count=Count(
                    "registrations",
                    filter=Q(registrations__status=EventRegistration.STATUS_REGISTERED),
                    distinct=True,
                )
            )
            .order_by("event_date")
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        member = self.request.user.member_profile
        event_ids = list(self.get_queryset().values_list("id", flat=True))
        context["event_registrations"] = {
            registration.event_id: registration
            for registration in EventRegistration.objects.filter(member=member, event_id__in=event_ids)
        }
        context["active_association_ids"] = set(
            Membership.objects.filter(member=member, status="active").values_list("association_id", flat=True)
        )
        return context


class EventListView(EventQuerysetMixin, generics.ListAPIView):
    pass


class EventDetailView(EventQuerysetMixin, generics.RetrieveAPIView):
    pass


class EventRegisterView(APIView):
    permission_classes = (IsAuthenticatedMember,)

    def post(self, request, identifier):
        event = Event.objects.filter(pk=identifier).first()
        if event is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            registration = register_for_event(member=request.user.member_profile, event=event)
        except EventRegistrationError as exc:
            return event_registration_error_response(exc)
        return Response(EventRegistrationSerializer(registration, context={"request": request}).data)


class EventCancelRegistrationView(APIView):
    permission_classes = (IsAuthenticatedMember,)

    def post(self, request, identifier):
        event = Event.objects.filter(pk=identifier).first()
        if event is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            registration = cancel_event_registration(member=request.user.member_profile, event=event)
        except EventRegistrationError as exc:
            status_code = status.HTTP_404_NOT_FOUND if exc.code == "event_registration_not_found" else status.HTTP_400_BAD_REQUEST
            return event_registration_error_response(exc, status_code=status_code)
        return Response(EventRegistrationSerializer(registration, context={"request": request}).data)


class EventRegistrationQuerysetMixin:
    serializer_class = EventRegistrationSerializer
    permission_classes = (IsAuthenticatedMember,)
    pagination_class = MemberPortalPagination
    lookup_url_kwarg = "identifier"

    def get_queryset(self):
        queryset = (
            EventRegistration.objects.filter(member=self.request.user.member_profile)
            .select_related("event", "event__association", "event__association__faculty")
            .order_by("-registered_at", "-id")
        )
        status_value = self.request.query_params.get("status")
        if status_value:
            valid_statuses = {choice[0] for choice in EventRegistration.STATUS_CHOICES}
            if status_value in valid_statuses:
                queryset = queryset.filter(status=status_value)
            else:
                queryset = queryset.none()
        return queryset


class EventRegistrationListView(EventRegistrationQuerysetMixin, generics.ListAPIView):
    pass


class EventRegistrationDetailView(EventRegistrationQuerysetMixin, generics.RetrieveAPIView):
    pass
