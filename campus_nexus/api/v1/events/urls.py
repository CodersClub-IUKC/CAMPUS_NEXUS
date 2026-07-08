from django.urls import path

from campus_nexus.api.v1.events.views import (
    EventCancelRegistrationView,
    EventDetailView,
    EventListView,
    EventRegisterView,
)

urlpatterns = [
    path("", EventListView.as_view(), name="member-events"),
    path("<int:identifier>/register/", EventRegisterView.as_view(), name="member-event-register"),
    path(
        "<int:identifier>/cancel-registration/",
        EventCancelRegistrationView.as_view(),
        name="member-event-cancel-registration",
    ),
    path("<int:identifier>/", EventDetailView.as_view(), name="member-event-detail"),
]
