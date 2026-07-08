from django.urls import path

from campus_nexus.api.v1.membership_applications.views import (
    MembershipApplicationCancelView,
    MembershipApplicationDetailView,
    MembershipApplicationListCreateView,
)

urlpatterns = [
    path("", MembershipApplicationListCreateView.as_view(), name="member-membership-applications"),
    path(
        "<int:identifier>/",
        MembershipApplicationDetailView.as_view(),
        name="member-membership-application-detail",
    ),
    path(
        "<int:identifier>/cancel/",
        MembershipApplicationCancelView.as_view(),
        name="member-membership-application-cancel",
    ),
]

