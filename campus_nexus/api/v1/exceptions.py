from rest_framework.exceptions import PermissionDenied


class MemberPortalAccessDenied(PermissionDenied):
    default_detail = "This account is not linked to a member portal profile."
    default_code = "member_portal_access_denied"

