from django.urls import path

from campus_nexus.api.v1.notification_preferences.views import MemberNotificationPreferenceView

urlpatterns = [
    path("", MemberNotificationPreferenceView.as_view(), name="member-notification-preferences"),
]
