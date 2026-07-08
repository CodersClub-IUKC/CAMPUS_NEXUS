from django.urls import path

from campus_nexus.api.v1.notifications.views import (
    NotificationDetailView,
    NotificationListView,
    NotificationReadAllView,
    NotificationReadView,
    NotificationUnreadCountView,
)

urlpatterns = [
    path("", NotificationListView.as_view(), name="member-notifications"),
    path("unread-count/", NotificationUnreadCountView.as_view(), name="member-notification-unread-count"),
    path("read-all/", NotificationReadAllView.as_view(), name="member-notification-read-all"),
    path("<int:identifier>/", NotificationDetailView.as_view(), name="member-notification-detail"),
    path("<int:identifier>/read/", NotificationReadView.as_view(), name="member-notification-read"),
]
