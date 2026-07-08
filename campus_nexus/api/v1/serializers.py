from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.authentication import default_user_authentication_rule
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from campus_nexus.models import (
    Announcement,
    Association,
    Course,
    Event,
    EventRegistration,
    Faculty,
    Member,
    Membership,
    MembershipApplication,
)
from campus_nexus.services.member_portal_finance import membership_financial_summary
from campus_nexus.services.membership_cards import membership_card_available
from campus_nexus.services.membership_eligibility import (
    association_membership_category,
    check_membership_eligibility,
)
from campus_nexus.services.membership_application import get_required_membership_fee


class FacultyBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = ("id", "name")


class CourseBriefSerializer(serializers.ModelSerializer):
    faculty = FacultyBriefSerializer(read_only=True)

    class Meta:
        model = Course
        fields = ("id", "name", "faculty")


class MemberProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    member_type_display = serializers.CharField(source="get_member_type_display", read_only=True)
    faculty = FacultyBriefSerializer(read_only=True)
    course = CourseBriefSerializer(read_only=True)

    class Meta:
        model = Member
        fields = (
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "registration_number",
            "national_id_number",
            "nationality",
            "member_type",
            "member_type_display",
            "faculty",
            "course",
            "photo",
            "created_at",
        )


class CurrentMemberSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="pk")
    username = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.SerializerMethodField()
    member = serializers.SerializerMethodField()

    def get_role(self, obj):
        return "member"

    def get_member(self, obj):
        return MemberProfileSerializer(obj.member_profile, context=self.context).data


class MemberTokenObtainPairSerializer(TokenObtainPairSerializer):
    default_error_messages = {
        "no_active_account": "No active member portal account found with the given credentials."
    }

    def validate(self, attrs):
        authenticate_kwargs = {
            self.username_field: attrs[self.username_field],
            "password": attrs["password"],
        }
        request = self.context.get("request")
        user = authenticate(request=request, **authenticate_kwargs)

        if user is None or not default_user_authentication_rule(user):
            self.fail("no_active_account")
        if not hasattr(user, "member_profile"):
            raise serializers.ValidationError(
                "This account is not linked to a member portal profile.",
                code="member_portal_access_denied",
            )

        self.user = user
        refresh = self.get_token(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": CurrentMemberSerializer(user, context=self.context).data,
        }


class AssociationBriefSerializer(serializers.ModelSerializer):
    association_type = serializers.SerializerMethodField()
    logo = serializers.ImageField(source="logo_image", read_only=True)
    theme = serializers.SerializerMethodField()

    class Meta:
        model = Association
        fields = ("id", "name", "association_type", "logo", "theme")

    def get_association_type(self, obj):
        return association_membership_category(obj)

    def get_theme(self, obj):
        return {
            "primary_color": obj.theme_primary_color or None,
            "secondary_color": obj.theme_secondary_color or None,
            "css_file": obj.theme_css_file.url if obj.theme_css_file else None,
            "version": obj.theme_version or None,
        }


class MembershipSerializer(serializers.ModelSerializer):
    association = AssociationBriefSerializer(read_only=True)
    total_paid = serializers.SerializerMethodField()
    outstanding_balance = serializers.SerializerMethodField()
    card_available = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = (
            "id",
            "association",
            "status",
            "joined_at",
            "subscription_anchor_date",
            "total_paid",
            "outstanding_balance",
            "card_available",
        )

    def get_total_paid(self, obj):
        return membership_financial_summary(obj)["total_paid"]

    def get_outstanding_balance(self, obj):
        return membership_financial_summary(obj)["outstanding_balance"]

    def get_card_available(self, obj):
        return membership_card_available(obj)


class AssociationSerializer(serializers.ModelSerializer):
    association_type = serializers.SerializerMethodField()
    faculty = FacultyBriefSerializer(read_only=True)
    logo = serializers.ImageField(source="logo_image", read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    upcoming_event_count = serializers.IntegerField(read_only=True)
    membership_fee = serializers.SerializerMethodField()
    current_membership_status = serializers.SerializerMethodField()
    eligibility = serializers.SerializerMethodField()
    application = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()
    theme = serializers.SerializerMethodField()

    class Meta:
        model = Association
        fields = (
            "id",
            "name",
            "description",
            "association_type",
            "faculty",
            "logo",
            "member_count",
            "membership_fee",
            "upcoming_event_count",
            "current_membership_status",
            "eligibility",
            "application",
            "actions",
            "theme",
            "created_at",
        )

    def get_association_type(self, obj):
        return association_membership_category(obj)

    def get_membership_fee(self, obj):
        fee = next((fee for fee in getattr(obj, "prefetched_fees", []) if fee.fee_type == "membership"), None)
        if fee is None:
            fee = obj.fees.filter(fee_type="membership").order_by("-created_at").first()
        return str(fee.amount) if fee else None

    def get_current_membership_status(self, obj):
        membership_statuses = self.context.get("membership_statuses", {})
        if obj.pk in membership_statuses:
            return membership_statuses[obj.pk]
        member = self.context["request"].user.member_profile
        membership = Membership.objects.filter(member=member, association=obj).only("status").first()
        return membership.status if membership else None

    def get_eligibility(self, obj):
        member = self.context["request"].user.member_profile
        return check_membership_eligibility(member, obj).as_dict()

    def get_application(self, obj):
        applications = self.context.get("applications", {})
        application = applications.get(obj.pk)
        if application is None:
            return {"id": None, "status": None, "status_display": None}
        return {
            "id": application.pk,
            "status": application.status,
            "status_display": application.get_status_display(),
        }

    def get_actions(self, obj):
        eligibility = self.get_eligibility(obj)
        application = self.get_application(obj)
        return {
            "can_apply": bool(eligibility["is_eligible"] and application["id"] is None),
        }

    def get_theme(self, obj):
        return {
            "primary_color": obj.theme_primary_color or None,
            "secondary_color": obj.theme_secondary_color or None,
            "css_file": obj.theme_css_file.url if obj.theme_css_file else None,
            "version": obj.theme_version or None,
        }


class EventSerializer(serializers.ModelSerializer):
    association = AssociationBriefSerializer(read_only=True)
    registration_status = serializers.SerializerMethodField()
    registration = serializers.SerializerMethodField()
    is_registered = serializers.SerializerMethodField()
    registered_count = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = (
            "id",
            "association",
            "title",
            "description",
            "event_date",
            "venue",
            "created_at",
            "registration_status",
            "registration",
            "is_registered",
            "registered_count",
            "actions",
        )

    def _registration(self, obj):
        registrations = self.context.get("event_registrations", {})
        if obj.pk in registrations:
            return registrations[obj.pk]
        request = self.context.get("request")
        if not request or not getattr(request.user, "is_authenticated", False):
            return None
        member = getattr(request.user, "member_profile", None)
        if member is None:
            return None
        return EventRegistration.objects.filter(event=obj, member=member).first()

    def _can_register(self, obj, registration):
        if registration and registration.status == EventRegistration.STATUS_REGISTERED:
            return False
        eligibility = self._eligibility(obj, registration)
        return eligibility["eligible"]

    def _eligibility(self, obj, registration):
        if obj.event_date < timezone.now():
            return {
                "eligible": False,
                "reason": "Registration is closed because this event has already started.",
                "reason_code": "event_ended",
            }
        if registration and registration.status == EventRegistration.STATUS_REGISTERED:
            return {
                "eligible": False,
                "reason": "You are already registered for this event.",
                "reason_code": "already_registered",
            }
        active_association_ids = set(self.context.get("active_association_ids", set()))
        if obj.association_id not in active_association_ids:
            return {
                "eligible": False,
                "reason": f"An active {obj.association.name} membership is required to register for this event.",
                "reason_code": "active_membership_required",
            }
        return {"eligible": True, "reason": "", "reason_code": ""}

    def get_registration_status(self, obj):
        registration = self._registration(obj)
        return registration.status if registration else None

    def get_registration(self, obj):
        registration = self._registration(obj)
        if registration is None:
            return None
        return {
            "id": registration.pk,
            "status": registration.status,
            "status_display": registration.get_status_display(),
            "registered_at": registration.registered_at,
            "cancelled_at": registration.cancelled_at,
        }

    def get_is_registered(self, obj):
        registration = self._registration(obj)
        return bool(registration and registration.status == EventRegistration.STATUS_REGISTERED)

    def get_registered_count(self, obj):
        annotated = getattr(obj, "registered_count", None)
        if annotated is not None:
            return annotated
        return obj.registrations.filter(status=EventRegistration.STATUS_REGISTERED).count()

    def get_actions(self, obj):
        registration = self._registration(obj)
        is_registered = bool(registration and registration.status == EventRegistration.STATUS_REGISTERED)
        eligibility = self._eligibility(obj, registration)
        return {
            "can_register": self._can_register(obj, registration),
            "can_cancel_registration": bool(is_registered and obj.event_date > timezone.now()),
            "reason": eligibility["reason"],
            "reason_code": eligibility["reason_code"],
        }


class AnnouncementSerializer(serializers.ModelSerializer):
    association = AssociationBriefSerializer(read_only=True)
    faculty = FacultyBriefSerializer(read_only=True)

    class Meta:
        model = Announcement
        fields = (
            "id",
            "title",
            "message",
            "audience",
            "association",
            "faculty",
            "is_published",
            "created_at",
        )


def membership_application_payment_data(application: MembershipApplication):
    charge = application.charge
    if charge:
        return {
            "required": True,
            "amount": str(charge.amount_due),
            "paid": str(charge.amount_paid_total),
            "balance": str(charge.balance),
            "status": charge.status,
            "charge_id": charge.pk,
        }

    try:
        fee = get_required_membership_fee(application.association)
    except Exception:
        return {
            "required": True,
            "amount": None,
            "paid": "0.00",
            "balance": None,
            "status": "not_configured",
            "charge_id": None,
        }

    return {
        "required": True,
        "amount": str(fee.amount),
        "paid": "0.00",
        "balance": str(fee.amount),
        "status": "not_generated",
        "charge_id": None,
    }


class MembershipApplicationSerializer(serializers.ModelSerializer):
    association = AssociationBriefSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment = serializers.SerializerMethodField()

    class Meta:
        model = MembershipApplication
        fields = (
            "id",
            "association",
            "status",
            "status_display",
            "applied_at",
            "reviewed_at",
            "rejection_reason",
            "payment",
        )

    def get_payment(self, obj):
        return membership_application_payment_data(obj)


class MembershipApplicationCreateSerializer(serializers.Serializer):
    association = serializers.PrimaryKeyRelatedField(queryset=Association.objects.all())
