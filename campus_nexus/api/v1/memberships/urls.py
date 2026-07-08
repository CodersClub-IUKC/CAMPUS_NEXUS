from django.urls import path

from campus_nexus.api.v1.memberships.views import MembershipCardView, MembershipDetailView, MembershipListView

urlpatterns = [
    path("", MembershipListView.as_view(), name="member-memberships"),
    path("<int:identifier>/", MembershipDetailView.as_view(), name="member-membership-detail"),
    path("<int:identifier>/card/", MembershipCardView.as_view(), name="member-membership-card"),
]
