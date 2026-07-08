from rest_framework import serializers

from campus_nexus.api.v1.serializers import AssociationBriefSerializer
from campus_nexus.models import Event, EventRegistration


class EventRegistrationEventSerializer(serializers.ModelSerializer):
    association = AssociationBriefSerializer(read_only=True)

    class Meta:
        model = Event
        fields = ("id", "association", "title", "event_date", "venue")


class EventRegistrationSerializer(serializers.ModelSerializer):
    event = EventRegistrationEventSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = EventRegistration
        fields = (
            "id",
            "event",
            "status",
            "status_display",
            "registered_at",
            "cancelled_at",
        )
