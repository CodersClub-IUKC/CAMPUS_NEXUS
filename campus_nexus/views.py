from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from campus_nexus.models import Faculty, Course, Association, Member, Cabinet, Payment, Event
from campus_nexus.serializers import (
    FacultySerializer,
    CourseSerializer,
    AssociationSerializer,
    MemberSerializer,
    CabinetSerializer,
    PaymentSerializer,
    EventSerializer
)   

class FacultyListView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)

    def get(self, request):
        faculties = Faculty.objects.all()
        serializer = FacultySerializer(faculties, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = FacultySerializer(data=request.data)
        if serializer.is_valid():
            faculty = serializer.save()
            return Response(FacultySerializer(faculty).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  
    
class FacultyDetailView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)

    def get(self, request, pk):
        try:
            faculty = Faculty.objects.get(pk=pk)
            serializer = FacultySerializer(faculty)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Faculty.DoesNotExist:
            return Response({"error": "Faculty not found"}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        try:
            faculty = Faculty.objects.get(pk=pk)
            serializer = FacultySerializer(faculty, data=request.data)
            if serializer.is_valid():
                updated_faculty = serializer.save()
                return Response(FacultySerializer(updated_faculty).data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Faculty.DoesNotExist:
            return Response({"error": "Faculty not found"}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            faculty = Faculty.objects.get(pk=pk)
            faculty.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Faculty.DoesNotExist:
            return Response({"error": "Faculty not found"}, status=status.HTTP_404_NOT_FOUND)   
        
class CourseListView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)
    
    def get(self, request):
        courses = Course.objects.all()
        serializer = CourseSerializer(courses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CourseSerializer(data=request.data)
        if serializer.is_valid():
            course = serializer.save()
            return Response(CourseSerializer(course).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class CourseDetailView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)
    
    def get(self, request, pk):
        try:
            course = Course.objects.get(pk=pk)
            serializer = CourseSerializer(course)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        try:
            course = Course.objects.get(pk=pk)
            serializer = CourseSerializer(course, data=request.data)
            if serializer.is_valid():
                updated_course = serializer.save()
                return Response(CourseSerializer(updated_course).data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            course = Course.objects.get(pk=pk)
            course.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)
        
class AssociationListView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)

    def get(self, request):
        associations = Association.objects.all()
        serializer = AssociationSerializer(associations, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = AssociationSerializer(data=request.data)
        if serializer.is_valid():
            association = serializer.save()
            return Response(AssociationSerializer(association).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AssociationDetailView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)

    def get(self, request, pk):
        try:
            association = Association.objects.get(pk=pk)
            serializer = AssociationSerializer(association)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Association.DoesNotExist:
            return Response({"error": "Association not found"}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        try:
            association = Association.objects.get(pk=pk)
            serializer = AssociationSerializer(association, data=request.data)
            if serializer.is_valid():
                updated_association = serializer.save()
                return Response(AssociationSerializer(updated_association).data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Association.DoesNotExist:
            return Response({"error": "Association not found"}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            association = Association.objects.get(pk=pk)
            association.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Association.DoesNotExist:
            return Response({"error": "Association not found"}, status=status.HTTP_404_NOT_FOUND)

class MemberListView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)

    def get(self, request):
        members = Member.objects.all()
        serializer = MemberSerializer(members, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = MemberSerializer(data=request.data)
        if serializer.is_valid():
            member = serializer.save()
            return Response(MemberSerializer(member).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MemberDetailView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)

    def get(self, request, pk):
        try:
            member = Member.objects.get(pk=pk)
            serializer = MemberSerializer(member)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Member.DoesNotExist:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        try:
            member = Member.objects.get(pk=pk)
            serializer = MemberSerializer(member, data=request.data)
            if serializer.is_valid():
                updated_member = serializer.save()
                return Response(MemberSerializer(updated_member).data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Member.DoesNotExist:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            member = Member.objects.get(pk=pk)
            member.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Member.DoesNotExist:
            return Response({"error": "Member not found"}, status=status.HTTP_404_NOT_FOUND)    

class CabinetListView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)
    def get(self, request):
        cabinets = Cabinet.objects.all()
        serializer = CabinetSerializer(cabinets, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CabinetSerializer(data=request.data)
        if serializer.is_valid():
            cabinet = serializer.save()
            return Response(CabinetSerializer(cabinet).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class CabinetDetailView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)
    def get(self, request, pk):
        try:
            cabinet = Cabinet.objects.get(pk=pk)
            serializer = CabinetSerializer(cabinet)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Cabinet.DoesNotExist:
            return Response({"error": "Cabinet not found"}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        try:
            cabinet = Cabinet.objects.get(pk=pk)
            serializer = CabinetSerializer(cabinet, data=request.data)
            if serializer.is_valid():
                updated_cabinet = serializer.save()
                return Response(CabinetSerializer(updated_cabinet).data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Cabinet.DoesNotExist:
            return Response({"error": "Cabinet not found"}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            cabinet = Cabinet.objects.get(pk=pk)
            cabinet.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Cabinet.DoesNotExist:
            return Response({"error": "Cabinet not found"}, status=status.HTTP_404_NOT_FOUND)   
        
class PaymentListView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)

    def get(self, request):
        payments = Payment.objects.all()
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = PaymentSerializer(data=request.data)
        if serializer.is_valid():
            payment = serializer.save()
            return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class PaymentDetailView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)

    def get(self, request, pk):
        try:
            payment = Payment.objects.get(pk=pk)
            serializer = PaymentSerializer(payment)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Payment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        try:
            payment = Payment.objects.get(pk=pk)
            serializer = PaymentSerializer(payment, data=request.data)
            if serializer.is_valid():
                updated_payment = serializer.save()
                return Response(PaymentSerializer(updated_payment).data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Payment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            payment = Payment.objects.get(pk=pk)
            payment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Payment.DoesNotExist:
            return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)   

class EventListView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)
    def get(self, request):
        events = Event.objects.all()
        serializer = EventSerializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = EventSerializer(data=request.data)
        if serializer.is_valid():
            event = serializer.save()
            return Response(EventSerializer(event).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class EventDetailView(APIView):
    # authentication_classes = (JWTAuthentication)
    # permission_classes = (IsAuthenticated)
    
    def get(self, request, pk):
        try:
            event = Event.objects.get(pk=pk)
            serializer = EventSerializer(event)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Event.DoesNotExist:
            return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, pk):
        try:
            event = Event.objects.get(pk=pk)
            serializer = EventSerializer(event, data=request.data)
            if serializer.is_valid():
                updated_event = serializer.save()
                return Response(EventSerializer(updated_event).data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Event.DoesNotExist:
            return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, pk):
        try:
            event = Event.objects.get(pk=pk)
            event.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Event.DoesNotExist:
            return Response({"error": "Event not found"}, status=status.HTTP_404_NOT_FOUND)
        
