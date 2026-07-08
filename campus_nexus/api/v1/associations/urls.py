from django.urls import path

from campus_nexus.api.v1.associations.views import AssociationDetailView, AssociationListView

urlpatterns = [
    path("", AssociationListView.as_view(), name="member-associations"),
    path("<int:identifier>/", AssociationDetailView.as_view(), name="member-association-detail"),
]

