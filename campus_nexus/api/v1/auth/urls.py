from django.urls import path

from campus_nexus.api.v1.auth.views import (
    CurrentMemberView,
    MemberLoginView,
    MemberLogoutView,
    MemberRefreshView,
)

urlpatterns = [
    path("login/", MemberLoginView.as_view(), name="member-login"),
    path("refresh/", MemberRefreshView.as_view(), name="member-refresh"),
    path("logout/", MemberLogoutView.as_view(), name="member-logout"),
    path("me/", CurrentMemberView.as_view(), name="member-me"),
]

