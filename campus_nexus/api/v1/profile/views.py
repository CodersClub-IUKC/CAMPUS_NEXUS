from rest_framework.response import Response
from rest_framework.views import APIView

from campus_nexus.api.v1.permissions import IsAuthenticatedMember
from campus_nexus.api.v1.serializers import MemberProfileSerializer


class MemberProfileView(APIView):
    permission_classes = (IsAuthenticatedMember,)

    def get(self, request):
        serializer = MemberProfileSerializer(request.user.member_profile, context={"request": request})
        return Response(serializer.data)

