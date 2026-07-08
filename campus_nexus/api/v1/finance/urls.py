from django.urls import path

from campus_nexus.api.v1.finance.views import (
    ChargeDetailView,
    ChargeListView,
    FinanceSummaryView,
    PaymentInstructionListView,
    PaymentDetailView,
    PaymentListView,
    PaymentReceiptView,
)

urlpatterns = [
    path("finance/summary/", FinanceSummaryView.as_view(), name="member-finance-summary"),
    path("charges/", ChargeListView.as_view(), name="member-charges"),
    path("charges/<int:identifier>/", ChargeDetailView.as_view(), name="member-charge-detail"),
    path("payments/", PaymentListView.as_view(), name="member-payments"),
    path("payments/<int:identifier>/", PaymentDetailView.as_view(), name="member-payment-detail"),
    path("payments/<int:identifier>/receipt/", PaymentReceiptView.as_view(), name="member-payment-receipt"),
    path("payment-instructions/", PaymentInstructionListView.as_view(), name="member-payment-instructions"),
]
