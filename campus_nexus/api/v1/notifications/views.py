from django.utils import timezone
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from campus_nexus.api.v1.notifications.serializers import NotificationSerializer
from campus_nexus.api.v1.pagination import MemberPortalPagination
from campus_nexus.api.v1.permissions import IsAuthenticatedMember
from campus_nexus.models import Notification


class NotificationQuerysetMixin:
    serializer_class = NotificationSerializer
    permission_classes = (IsAuthenticatedMember,)
    pagination_class = MemberPortalPagination
    lookup_url_kwarg = "identifier"

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).order_by("-created_at", "-id")


class NotificationListView(NotificationQuerysetMixin, generics.ListAPIView):
    pass


class NotificationDetailView(NotificationQuerysetMixin, generics.RetrieveAPIView):
    pass


class NotificationUnreadCountView(APIView):
    permission_classes = (IsAuthenticatedMember,)

    def get(self, request):
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({"unread_count": unread_count})


class NotificationReadView(NotificationQuerysetMixin, generics.GenericAPIView):
    def post(self, request, identifier):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return Response(NotificationSerializer(notification, context=self.get_serializer_context()).data)


class NotificationReadAllView(APIView):
    permission_classes = (IsAuthenticatedMember,)

    def post(self, request):
        now = timezone.now()
        queryset = Notification.objects.filter(recipient=request.user, is_read=False)
        updated_count = queryset.update(is_read=True, read_at=now)
        return Response({"updated_count": updated_count})
