from django.utils import timezone
from rest_framework import serializers

from campus_nexus.models import Membership
from campus_nexus.services.membership_cards import (
    mask_registration_number,
    membership_card_available,
    membership_verification_path,
)


def _file_url(field):
    if not field:
        return None
    try:
        return field.url
    except ValueError:
        return None


def association_theme(association):
    return {
        "primary_color": association.theme_primary_color or None,
        "secondary_color": association.theme_secondary_color or None,
        "css_file": _file_url(association.theme_css_file),
        "version": association.theme_version or None,
    }


class MembershipCardSerializer(serializers.ModelSerializer):
    membership = serializers.SerializerMethodField()
    member = serializers.SerializerMethodField()
    association = serializers.SerializerMethodField()
    card = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ("membership", "member", "association", "card")

    def get_membership(self, obj):
        return {
            "id": obj.pk,
            "status": obj.status,
            "status_display": obj.get_status_display(),
            "member_since": obj.joined_at.date() if obj.joined_at else None,
        }

    def get_member(self, obj):
        member = obj.member
        return {
            "full_name": member.full_name,
            "registration_number": member.registration_number,
            "profile_photo": _file_url(member.photo),
        }

    def get_association(self, obj):
        association = obj.association
        return {
            "id": association.pk,
            "name": association.name,
            "logo": _file_url(association.logo_image),
            "theme": association_theme(association),
        }

    def get_card(self, obj):
        available = membership_card_available(obj)
        return {
            "available": available,
            "verification_token": str(obj.verification_token) if available else None,
            "verification_path": membership_verification_path(obj) if available else None,
        }


class PublicMembershipVerificationSerializer(serializers.ModelSerializer):
    valid = serializers.SerializerMethodField()
    verification_status = serializers.SerializerMethodField()
    verification_status_display = serializers.SerializerMethodField()
    member = serializers.SerializerMethodField()
    association = serializers.SerializerMethodField()
    membership = serializers.SerializerMethodField()
    verified_at = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = (
            "valid",
            "verification_status",
            "verification_status_display",
            "member",
            "association",
            "membership",
            "verified_at",
        )

    def get_valid(self, obj):
        return membership_card_available(obj)

    def get_verification_status(self, obj):
        return "active" if membership_card_available(obj) else "inactive"

    def get_verification_status_display(self, obj):
        return "Valid Membership" if membership_card_available(obj) else "Membership Not Active"

    def get_member(self, obj):
        if not membership_card_available(obj):
            return None
        member = obj.member
        return {
            "display_name": member.full_name,
            "registration_number": mask_registration_number(member.registration_number),
        }

    def get_association(self, obj):
        association = obj.association
        data = {"name": association.name}
        logo = _file_url(association.logo_image)
        if logo:
            data["logo"] = logo
        return data

    def get_membership(self, obj):
        return {
            "status": obj.status,
            "status_display": obj.get_status_display(),
            "member_since": obj.joined_at.date() if obj.joined_at else None,
        }

    def get_verified_at(self, obj):
        return timezone.now()
