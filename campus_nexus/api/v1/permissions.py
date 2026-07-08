from rest_framework.permissions import BasePermission


class IsAuthenticatedMember(BasePermission):
    message = "This endpoint is available only to authenticated member portal users."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return hasattr(user, "member_profile")

