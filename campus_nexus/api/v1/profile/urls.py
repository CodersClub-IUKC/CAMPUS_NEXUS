from django.urls import path

from campus_nexus.api.v1.profile.views import MemberProfileView

urlpatterns = [
    path("", MemberProfileView.as_view(), name="member-profile"),
]

