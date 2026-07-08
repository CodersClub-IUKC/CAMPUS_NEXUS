from django.urls import path

from campus_nexus.api.v1.feedback.views import MemberFeedbackDetailView, MemberFeedbackListCreateView

urlpatterns = [
    path("", MemberFeedbackListCreateView.as_view(), name="member-feedback"),
    path("<int:identifier>/", MemberFeedbackDetailView.as_view(), name="member-feedback-detail"),
]
