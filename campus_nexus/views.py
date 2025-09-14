from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import MultiPartParser, FormParser

from campus_nexus.models import (
    Faculty, Course, Association, Member,
    Cabinet, Payment, Event, Membership, Fee
)
from campus_nexus.serializers import (
    FacultySerializer,
    CourseSerializer,
    AssociationSerializer,
    MemberSerializer,
    CabinetSerializer,
    PaymentSerializer,
    EventSerializer,
    MembershipSerializer,
    FeeSerializer
)


# Base view with JWT + IsAuthenticated
class BaseAuthenticatedView:
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)


# Faculty
class FacultyListView(BaseAuthenticatedView, generics.ListCreateAPIView):
    queryset = Faculty.objects.all()
    serializer_class = FacultySerializer


class FacultyDetailView(BaseAuthenticatedView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Faculty.objects.all()
    serializer_class = FacultySerializer


# Course
class CourseListView(BaseAuthenticatedView, generics.ListCreateAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer


class CourseDetailView(BaseAuthenticatedView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer


# Association
class AssociationListView(BaseAuthenticatedView, generics.ListCreateAPIView):
    queryset = Association.objects.all()
    serializer_class = AssociationSerializer
    parser_classes = (MultiPartParser, FormParser)  # handle logo upload


class AssociationDetailView(BaseAuthenticatedView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Association.objects.all()
    serializer_class = AssociationSerializer
    parser_classes = (MultiPartParser, FormParser)


# Member
class MemberListView(BaseAuthenticatedView, generics.ListCreateAPIView):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer


class MemberDetailView(BaseAuthenticatedView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer


# -Cabinet
class CabinetListView(BaseAuthenticatedView, generics.ListCreateAPIView):
    queryset = Cabinet.objects.all()
    serializer_class = CabinetSerializer


class CabinetDetailView(BaseAuthenticatedView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Cabinet.objects.all()
    serializer_class = CabinetSerializer


#  Payment
class PaymentListView(BaseAuthenticatedView, generics.ListCreateAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    parser_classes = (MultiPartParser, FormParser)  # handle receipt upload


class PaymentDetailView(BaseAuthenticatedView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    parser_classes = (MultiPartParser, FormParser)


# Event
class EventListView(BaseAuthenticatedView, generics.ListCreateAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer


class EventDetailView(BaseAuthenticatedView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Event.objects.all()
    serializer_class = EventSerializer


# Membership
class MembershipListView(BaseAuthenticatedView, generics.ListCreateAPIView):
    queryset = Membership.objects.all()
    serializer_class = MembershipSerializer


class MembershipDetailView(BaseAuthenticatedView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Membership.objects.all()
    serializer_class = MembershipSerializer


# Fee
class FeeListView(BaseAuthenticatedView, generics.ListCreateAPIView):
    queryset = Fee.objects.all()
    serializer_class = FeeSerializer


class FeeDetailView(BaseAuthenticatedView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Fee.objects.all()
    serializer_class = FeeSerializer