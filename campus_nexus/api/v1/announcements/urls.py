from django.urls import path

from campus_nexus.api.v1.announcements.views import AnnouncementDetailView, AnnouncementListView

urlpatterns = [
    path("", AnnouncementListView.as_view(), name="member-announcements"),
    path("<int:identifier>/", AnnouncementDetailView.as_view(), name="member-announcement-detail"),
]

