from rest_framework import serializers

from campus_nexus.models import MemberNotificationPreference


class MemberNotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberNotificationPreference
        fields = ("event_notifications", "announcement_notifications")

    def to_internal_value(self, data):
        unknown_fields = set(data) - set(self.fields)
        if unknown_fields:
            raise serializers.ValidationError(
                {field: ["This preference is not supported."] for field in sorted(unknown_fields)}
            )
        return super().to_internal_value(data)
