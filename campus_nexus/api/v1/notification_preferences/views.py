from rest_framework.response import Response
from rest_framework.views import APIView

from campus_nexus.api.v1.notification_preferences.serializers import MemberNotificationPreferenceSerializer
from campus_nexus.api.v1.permissions import IsAuthenticatedMember
from campus_nexus.services.audit import record_audit_event
from campus_nexus.services.notification_preferences import (
    get_member_notification_preferences,
    update_member_notification_preferences,
)


class MemberNotificationPreferenceView(APIView):
    permission_classes = (IsAuthenticatedMember,)

    def get(self, request):
        preferences = get_member_notification_preferences(request.user.member_profile)
        return Response(MemberNotificationPreferenceSerializer(preferences).data)

    def patch(self, request):
        member = request.user.member_profile
        serializer = MemberNotificationPreferenceSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        preferences, changes = update_member_notification_preferences(member, serializer.validated_data)
        if changes:
            record_audit_event(
                actor=request.user,
                action="NOTIFICATION_PREFERENCES_UPDATED",
                obj=preferences,
                metadata=changes,
            )
        return Response(MemberNotificationPreferenceSerializer(preferences).data)
