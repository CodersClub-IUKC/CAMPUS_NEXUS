from django.urls import path
from .views import EventDetailView, EventListView, FacultyListView, CourseListView, AssociationListView, MemberListView, \
    FacultyDetailView, MemberDetailView, CourseDetailView, AssociationDetailView

urlpatterns = [
    path('faculties/', FacultyListView.as_view(), name='faculty-list'),
    path('faculties/<int:pk>/', FacultyDetailView.as_view(), name='faculty-detail'),
    path('courses/', CourseListView.as_view(), name='course-list'),
    path('courses/<int:pk>/', CourseDetailView.as_view(), name='course-detail'),
    path('associations/', AssociationListView.as_view(), name='association-list'),
    path('associations/<int:pk>/', AssociationDetailView.as_view(), name='association-detail'),
    path('members/', MemberListView.as_view(), name='member-list'),
    path('members/<int:pk>/', MemberDetailView.as_view(), name='member-detail'),
    path('events/', EventListView.as_view(), name='event-list'),
    path('events/<int:pk>/', EventDetailView.as_view(), name='event-detail'),
    ]