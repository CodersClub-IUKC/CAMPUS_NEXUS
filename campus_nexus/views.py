from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.parsers import MultiPartParser, FormParser

from campus_nexus.models import (
    Faculty, Course, Association, Member,
    Cabinet, Payment, Event, Membership, Fee, Feedback
)
from campus_nexus.serializers import ( CabinetMemberSerializer,
    FacultySerializer, CourseSerializer, AssociationSerializer, MemberSerializer,
    CabinetSerializer, PaymentSerializer, EventSerializer, MembershipSerializer, FeeSerializer, FeedbackSerializer
)

import hmac
import hashlib
import subprocess
import os
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

# This secret MUST match your GitHub webhook secret
SECRET = b"django-insecure-2bvf7*#lntuaw8ga$5vgu8ytb3d(3ct4ir8q-bb27$py%*4_rc"

@csrf_exempt
def github_deploy(request):
    if request.method != "POST":
        return HttpResponseForbidden("Only POST allowed")

    # Verify GitHub signature
    header_signature = request.headers.get("X-Hub-Signature-256")
    if not header_signature:
        return HttpResponseForbidden("Missing signature")

    sha_name, signature = header_signature.split("=")
    if sha_name != "sha256":
        return HttpResponseForbidden("Invalid signature format")

    mac = hmac.new(SECRET, msg=request.body, digestmod=hashlib.sha256)
    if not hmac.compare_digest(mac.hexdigest(), signature):
        return HttpResponseForbidden("Invalid signature")

    # Run deploy script asynchronously
    subprocess.Popen(["/bin/bash", os.path.expanduser("~/your_project_directory/deploy.sh")])

    return HttpResponse("✅ Deployment started", status=200)


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

# -Cabinet Member
class CabinetMemberListView(BaseAuthenticatedView, generics.ListCreateAPIView):
    queryset = Cabinet.objects.all()
    serializer_class = CabinetMemberSerializer

class CabinetMemberDetailView(BaseAuthenticatedView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Cabinet.objects.all()
    serializer_class = CabinetMemberSerializer

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


#Feedback
class FeedbackListView(BaseAuthenticatedView, generics.ListCreateAPIView):
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer

class FeedbackDetailView(BaseAuthenticatedView, generics.RetrieveUpdateDestroyAPIView):
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer