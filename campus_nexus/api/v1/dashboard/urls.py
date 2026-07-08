from django.urls import path

from campus_nexus.api.v1.dashboard.views import MemberDashboardView

urlpatterns = [
    path("", MemberDashboardView.as_view(), name="member-dashboard"),
]

