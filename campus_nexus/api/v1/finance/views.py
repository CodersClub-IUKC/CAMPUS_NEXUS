from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from campus_nexus.api.v1.finance.serializers import (
    ChargeDetailSerializer,
    ChargeListSerializer,
    PaymentInstructionSerializer,
    PaymentDetailSerializer,
    PaymentListSerializer,
)
from campus_nexus.api.v1.pagination import MemberPortalPagination
from campus_nexus.api.v1.permissions import IsAuthenticatedMember
from campus_nexus.models import AssociationPaymentInstruction, Charge, Payment
from campus_nexus.services.member_finance import (
    get_member_charge_queryset,
    get_member_finance_summary,
    get_member_payment_queryset,
)


class FinanceSummaryView(APIView):
    permission_classes = (IsAuthenticatedMember,)

    def get(self, request):
        return Response(get_member_finance_summary(request.user.member_profile))


class ChargeQuerysetMixin:
    permission_classes = (IsAuthenticatedMember,)
    pagination_class = MemberPortalPagination
    lookup_url_kwarg = "identifier"

    def get_queryset(self):
        queryset = get_member_charge_queryset(self.request.user.member_profile)
        status_value = self.request.query_params.get("status")
        if status_value:
            valid_statuses = {choice[0] for choice in Charge.STATUS_CHOICES}
            if status_value in valid_statuses:
                queryset = queryset.filter(status=status_value)
            else:
                queryset = queryset.none()
        return queryset


class ChargeListView(ChargeQuerysetMixin, generics.ListAPIView):
    serializer_class = ChargeListSerializer


class ChargeDetailView(ChargeQuerysetMixin, generics.RetrieveAPIView):
    serializer_class = ChargeDetailSerializer


class PaymentQuerysetMixin:
    permission_classes = (IsAuthenticatedMember,)
    pagination_class = MemberPortalPagination
    lookup_url_kwarg = "identifier"

    def get_queryset(self):
        queryset = get_member_payment_queryset(self.request.user.member_profile)
        status_value = self.request.query_params.get("status")
        if status_value:
            valid_statuses = {choice[0] for choice in Payment.STATUS_CHOICES}
            if status_value in valid_statuses:
                queryset = queryset.filter(status=status_value)
            else:
                queryset = queryset.none()
        association_id = self.request.query_params.get("association")
        if association_id:
            queryset = queryset.filter(membership__association_id=association_id)
        return queryset


class PaymentListView(PaymentQuerysetMixin, generics.ListAPIView):
    serializer_class = PaymentListSerializer


class PaymentDetailView(PaymentQuerysetMixin, generics.RetrieveAPIView):
    serializer_class = PaymentDetailSerializer


class PaymentInstructionListView(generics.ListAPIView):
    serializer_class = PaymentInstructionSerializer
    permission_classes = (IsAuthenticatedMember,)
    pagination_class = MemberPortalPagination

    def get_queryset(self):
        member = self.request.user.member_profile
        association_ids = (
            Charge.objects.filter(membership__member=member)
            .exclude(status__in=["paid", "cancelled"])
            .values_list("association_id", flat=True)
            .distinct()
        )
        return (
            AssociationPaymentInstruction.objects.filter(
                association_id__in=association_ids,
                payment_method="cash",
                is_active=True,
            )
            .select_related("association")
            .order_by("association__name", "payment_method", "-updated_at", "-id")
        )


class PaymentReceiptView(APIView):
    permission_classes = (IsAuthenticatedMember,)

    def get(self, request, identifier):
        payment_exists = get_member_payment_queryset(request.user.member_profile).filter(pk=identifier).exists()
        if not payment_exists:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "detail": (
                    "PDF receipt generation is not available yet. "
                    "The current backend stores receipt images but has no safe PDF receipt architecture."
                )
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
