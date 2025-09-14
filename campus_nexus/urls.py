from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from .views import (
    FacultyListView, FacultyDetailView,
    CourseListView, CourseDetailView,
    AssociationListView, AssociationDetailView,
    MemberListView, MemberDetailView,
    EventListView, EventDetailView,
    CabinetListView, CabinetDetailView,
    PaymentListView, PaymentDetailView,
    MembershipListView, MembershipDetailView,
    FeeListView, FeeDetailView, CabinetMemberListView, CabinetMemberDetailView
)

urlpatterns = [
    # Faculties
    path('faculties/', FacultyListView.as_view(), name='faculty-list'),
    path('faculties/<int:pk>/', FacultyDetailView.as_view(), name='faculty-detail'),

    # Courses
    path('courses/', CourseListView.as_view(), name='course-list'),
    path('courses/<int:pk>/', CourseDetailView.as_view(), name='course-detail'),

    # Associations
    path('associations/', AssociationListView.as_view(), name='association-list'),
    path('associations/<int:pk>/', AssociationDetailView.as_view(), name='association-detail'),

    # Members
    path('members/', MemberListView.as_view(), name='member-list'),
    path('members/<int:pk>/', MemberDetailView.as_view(), name='member-detail'),

    # Events
    path('events/', EventListView.as_view(), name='event-list'),
    path('events/<int:pk>/', EventDetailView.as_view(), name='event-detail'),

    # Cabinets
    path('cabinets/', CabinetListView.as_view(), name='cabinet-list'),
    path('cabinets/<int:pk>/', CabinetDetailView.as_view(), name='cabinet-detail'),

    #Cabinet Members
    path('cabinet-members/', CabinetMemberListView.as_view(), name='cabinet-member-list'),
    path('cabinet-members/<int:pk>/', CabinetMemberDetailView.as_view(), name='cabinet-member-detail'),

    # Payments
    path('payments/', PaymentListView.as_view(), name='payment-list'),
    path('payments/<int:pk>/', PaymentDetailView.as_view(), name='payment-detail'),

    # Memberships
    path('memberships/', MembershipListView.as_view(), name='membership-list'),
    path('memberships/<int:pk>/', MembershipDetailView.as_view(), name='membership-detail'),

    # Fees
    path('fees/', FeeListView.as_view(), name='fee-list'),
    path('fees/<int:pk>/', FeeDetailView.as_view(), name='fee-detail'),
]

# serve media files in dev (images like logos/receipts)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
