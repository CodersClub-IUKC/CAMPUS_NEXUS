
from rest_framework import serializers
from campus_nexus.models import Faculty, Course, Association, Member, Cabinet, Payment, Event


class FacultySerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = '__all__'      

    def create(self, validated_data):
        faculty = Faculty.objects.create(**validated_data)
        return faculty

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.save()
        return instance

class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = '__all__'

    def create(self, validated_data):
        course = Course.objects.create(**validated_data)
        return course

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.duration_years = validated_data.get('duration_years', instance.duration_years)
        instance.save()
        return instance

class AssociationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Association
        fields = '__all__'

    def create(self, validated_data):
        association = Association.objects.create(**validated_data)
        return association

    def update(self, instance, validated_data):
        instance.name = validated_data.get('name', instance.name)
        instance.description = validated_data.get('description', instance.description)
        instance.logo_url = validated_data.get('logo_url', instance.logo_url)
        instance.save()
        return instance

class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = '__all__'

    def create(self, validated_data):
        member = Faculty.member.objects.create(**validated_data)
        return member
    
    def update(self, instance, validated_data):
        instance.full_name = validated_data.get('full_name', instance.full_name)
        instance.email = validated_data.get('email', instance.email)
        instance.phone = validated_data.get('phone', instance.phone)
        instance.registration_number = validated_data.get('registration_number', instance.registration_number)
        instance.national_id_number = validated_data.get('national_id_number', instance.national_id_number)
        instance.member_type = validated_data.get('member_type', instance.member_type)
        instance.faculty = validated_data.get('faculty', instance.faculty)
        instance.course = validated_data.get('course', instance.course)
        instance.save()
        return instance

    
class CabinetSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    logo_url = serializers.URLField(required=False, allow_blank=True)

    def create(self, validated_data):
        # Custom logic to create a cabinet instance
        pass

    def update(self, instance, validated_data):
        # Custom logic to update a cabinet instance
        pass    

class PaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_method = serializers.ChoiceField(choices=['credit_card', 'bank_transfer', 'mobile_money'])
    transaction_id = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def create(self, validated_data):
        # Custom logic to create a payment instance
        pass

    def update(self, instance, validated_data):
        # Custom logic to update a payment instance
        pass    

class EventSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    date = serializers.DateTimeField()
    location = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def create(self, validated_data):
        # Custom logic to create an event instance
        pass

    def update(self, instance, validated_data):
        # Custom logic to update an event instance
        pass    

class FeeSerializer(serializers.Serializer):    
    fee_type = serializers.ChoiceField(choices=['membership', 'subscription'])
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    duration_months = serializers.IntegerField()

    def create(self, validated_data):
        # Custom logic to create a fee instance
        pass

    def update(self, instance, validated_data):
        # Custom logic to update a fee instance
        pass    

class MembershipSerializer(serializers.Serializer):
    member = serializers.PrimaryKeyRelatedField(queryset=Member.objects.all())
    association = serializers.PrimaryKeyRelatedField(queryset=Association.objects.all())
    status = serializers.ChoiceField(choices=['active', 'inactive', 'pending'])
    start_date = serializers.DateField()
    end_date = serializers.DateField(required=False, allow_null=True)

    def create(self, validated_data):
        # Custom logic to create a membership instance
        pass

    def update(self, instance, validated_data):
        # Custom logic to update a membership instance
        pass