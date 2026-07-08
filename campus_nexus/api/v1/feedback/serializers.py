from rest_framework import serializers

from campus_nexus.api.v1.serializers import AssociationBriefSerializer
from campus_nexus.models import Association, Feedback


class MemberFeedbackSerializer(serializers.ModelSerializer):
    association = AssociationBriefSerializer(read_only=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_at = serializers.DateTimeField(source="submitted_at", read_only=True)

    class Meta:
        model = Feedback
        fields = (
            "id",
            "category",
            "category_display",
            "subject",
            "message",
            "status",
            "status_display",
            "association",
            "admin_response",
            "responded_at",
            "created_at",
            "updated_at",
        )


class MemberFeedbackCreateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=Feedback.CATEGORY_CHOICES, default=Feedback.CATEGORY_GENERAL)
    association = serializers.PrimaryKeyRelatedField(
        queryset=Association.objects.all(),
        required=False,
        allow_null=True,
    )
    subject = serializers.CharField(max_length=200, trim_whitespace=True)
    message = serializers.CharField(trim_whitespace=True)

    def to_internal_value(self, data):
        unknown_fields = set(data) - set(self.fields)
        if unknown_fields:
            raise serializers.ValidationError(
                {field: ["This field is not supported."] for field in sorted(unknown_fields)}
            )
        return super().to_internal_value(data)

    def validate_subject(self, value):
        if not value.strip():
            raise serializers.ValidationError("Subject is required.")
        return value.strip()

    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError("Message is required.")
        return value.strip()
