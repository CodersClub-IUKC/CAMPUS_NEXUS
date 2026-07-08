from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from campus_nexus.api.v1.permissions import IsAuthenticatedMember
from campus_nexus.api.v1.serializers import CurrentMemberSerializer, MemberTokenObtainPairSerializer


class MemberLoginView(TokenObtainPairView):
    serializer_class = MemberTokenObtainPairSerializer


class MemberRefreshView(TokenRefreshView):
    pass


class MemberLogoutView(APIView):
    permission_classes = (IsAuthenticatedMember,)

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError:
            return Response({"detail": "Invalid refresh token."}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentMemberView(APIView):
    permission_classes = (IsAuthenticatedMember,)

    def get(self, request):
        serializer = CurrentMemberSerializer(request.user, context={"request": request})
        return Response(serializer.data)

