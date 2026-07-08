from rest_framework import serializers

from campus_nexus.api.v1.serializers import AssociationBriefSerializer
from campus_nexus.models import AssociationPaymentInstruction, Charge, Payment
from campus_nexus.services.member_finance import charge_recorded_balance, charge_recorded_paid
from campus_nexus.services.member_portal_finance import decimal_string


class ChargeFeeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(source="get_fee_type_display")
    fee_type = serializers.CharField()


class ChargeMembershipSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()


class ChargeListSerializer(serializers.ModelSerializer):
    association = AssociationBriefSerializer(read_only=True)
    membership = ChargeMembershipSerializer(read_only=True)
    fee = ChargeFeeSerializer(read_only=True)
    purpose_display = serializers.CharField(source="get_purpose_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    amount = serializers.SerializerMethodField()
    paid_amount = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Charge
        fields = (
            "id",
            "purpose",
            "purpose_display",
            "title",
            "description",
            "association",
            "membership",
            "fee",
            "amount",
            "paid_amount",
            "balance",
            "status",
            "status_display",
            "due_date",
            "period_start",
            "period_end",
            "is_overdue",
            "created_at",
        )

    def get_amount(self, obj):
        return decimal_string(obj.amount_due)

    def get_paid_amount(self, obj):
        return decimal_string(charge_recorded_paid(obj))

    def get_balance(self, obj):
        return decimal_string(charge_recorded_balance(obj))


class ChargePaymentSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ("id", "amount", "paid_at", "recorded_at", "payment_method", "reference_code", "status")

    def get_amount(self, obj):
        return decimal_string(obj.amount_paid)


class ChargeDetailSerializer(ChargeListSerializer):
    payments = serializers.SerializerMethodField()
    activation_context = serializers.SerializerMethodField()
    payment_guidance = serializers.SerializerMethodField()

    class Meta(ChargeListSerializer.Meta):
        fields = ChargeListSerializer.Meta.fields + ("payments", "activation_context", "payment_guidance")

    def get_payments(self, obj):
        payments = obj.payments.order_by("-paid_at", "-recorded_at", "-id")
        return ChargePaymentSerializer(payments, many=True, context=self.context).data

    def get_activation_context(self, obj):
        application = getattr(obj, "membership_application", None)
        if application is None:
            return None
        return {
            "requires_full_payment_for_membership": obj.purpose == "membership_fee",
            "membership_status": application.membership.status if application.membership_id else None,
            "application_status": application.status,
        }

    def get_payment_guidance(self, obj):
        instruction = (
            AssociationPaymentInstruction.objects.filter(
                association_id=obj.association_id,
                payment_method="cash",
                is_active=True,
            )
            .order_by("-updated_at", "-id")
            .first()
        )
        if instruction is None:
            return None
        return PaymentInstructionSerializer(instruction, context=self.context).data


class PaymentChargeSerializer(serializers.ModelSerializer):
    purpose_display = serializers.CharField(source="get_purpose_display", read_only=True)
    amount = serializers.SerializerMethodField()
    paid_amount = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Charge
        fields = (
            "id",
            "purpose",
            "purpose_display",
            "title",
            "amount",
            "paid_amount",
            "balance",
            "status",
        )

    def get_amount(self, obj):
        return decimal_string(obj.amount_due)

    def get_paid_amount(self, obj):
        return decimal_string(charge_recorded_paid(obj))

    def get_balance(self, obj):
        return decimal_string(charge_recorded_balance(obj))


class PaymentListSerializer(serializers.ModelSerializer):
    association = serializers.SerializerMethodField()
    charge = PaymentChargeSerializer(read_only=True)
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = (
            "id",
            "reference_code",
            "amount",
            "paid_at",
            "recorded_at",
            "payment_method",
            "status",
            "association",
            "charge",
        )

    def get_amount(self, obj):
        return decimal_string(obj.amount_paid)

    def get_association(self, obj):
        association = obj.membership.association
        return {
            "id": association.pk,
            "name": association.name,
        }


class PaymentDetailSerializer(PaymentListSerializer):
    fee = ChargeFeeSerializer(read_only=True)

    class Meta(PaymentListSerializer.Meta):
        fields = PaymentListSerializer.Meta.fields + ("fee",)


class PaymentInstructionSerializer(serializers.ModelSerializer):
    association = AssociationBriefSerializer(read_only=True)
    payment_method_display = serializers.CharField(source="get_payment_method_display", read_only=True)

    class Meta:
        model = AssociationPaymentInstruction
        fields = (
            "id",
            "association",
            "payment_method",
            "payment_method_display",
            "payment_location",
            "pay_to",
            "contact_phone",
            "instructions",
        )
