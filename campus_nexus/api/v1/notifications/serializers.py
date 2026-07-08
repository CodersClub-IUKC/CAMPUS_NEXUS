from rest_framework import serializers

from campus_nexus.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(source="get_notification_type_display", read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id",
            "title",
            "message",
            "notification_type",
            "notification_type_display",
            "is_read",
            "created_at",
            "read_at",
            "related_url",
        )
