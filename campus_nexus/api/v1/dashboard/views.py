from rest_framework.response import Response
from rest_framework.views import APIView

from campus_nexus.api.v1.dashboard.services import build_member_dashboard
from campus_nexus.api.v1.permissions import IsAuthenticatedMember


class MemberDashboardView(APIView):
    permission_classes = (IsAuthenticatedMember,)

    def get(self, request):
        return Response(build_member_dashboard(request.user.member_profile, request))

