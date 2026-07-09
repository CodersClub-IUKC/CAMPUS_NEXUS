from rest_framework import serializers

from campus_nexus.services.member_password_reset import (
    GENERIC_PASSWORD_RESET_DETAIL,
    confirm_member_password_reset,
    request_member_password_reset,
    token_is_valid_for_member_portal_user,
)


class PasswordResetRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=150, trim_whitespace=True)

    def save(self, **kwargs):
        request_member_password_reset(
            self.validated_data["identifier"],
            request=self.context.get("request"),
        )
        return {"detail": GENERIC_PASSWORD_RESET_DETAIL}


class PasswordResetValidateSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=256, trim_whitespace=True)
    token = serializers.CharField(max_length=256, trim_whitespace=True)

    def validate(self, attrs):
        valid, _user = token_is_valid_for_member_portal_user(attrs["uid"], attrs["token"])
        attrs["valid"] = valid
        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=256, trim_whitespace=True)
    token = serializers.CharField(max_length=256, trim_whitespace=True)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": ["Passwords do not match."]}
            )
        return attrs

    def save(self, **kwargs):
        success, errors = confirm_member_password_reset(
            self.validated_data["uid"],
            self.validated_data["token"],
            self.validated_data["new_password"],
        )
        if not success:
            raise serializers.ValidationError(errors)
        return {
            "detail": "Your password has been reset successfully. You can now sign in."
        }
