from django.urls import include, path

from campus_nexus.api.v1.memberships.views import PublicMembershipVerificationView

urlpatterns = [
    path(
        "public/membership-verification/<uuid:token>/",
        PublicMembershipVerificationView.as_view(),
        name="public-membership-verification",
    ),
    path("", include("campus_nexus.api.v1.finance.urls")),
    path("auth/", include("campus_nexus.api.v1.auth.urls")),
    path("dashboard/", include("campus_nexus.api.v1.dashboard.urls")),
    path("event-registrations/", include("campus_nexus.api.v1.event_registrations.urls")),
    path("profile/", include("campus_nexus.api.v1.profile.urls")),
    path("memberships/", include("campus_nexus.api.v1.memberships.urls")),
    path("membership-applications/", include("campus_nexus.api.v1.membership_applications.urls")),
    path("notification-preferences/", include("campus_nexus.api.v1.notification_preferences.urls")),
    path("notifications/", include("campus_nexus.api.v1.notifications.urls")),
    path("associations/", include("campus_nexus.api.v1.associations.urls")),
    path("events/", include("campus_nexus.api.v1.events.urls")),
    path("feedback/", include("campus_nexus.api.v1.feedback.urls")),
    path("announcements/", include("campus_nexus.api.v1.announcements.urls")),
]
