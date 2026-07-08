from django.urls import path

from campus_nexus.api.v1.events.views import EventRegistrationDetailView, EventRegistrationListView

urlpatterns = [
    path("", EventRegistrationListView.as_view(), name="member-event-registrations"),
    path("<int:identifier>/", EventRegistrationDetailView.as_view(), name="member-event-registration-detail"),
]
