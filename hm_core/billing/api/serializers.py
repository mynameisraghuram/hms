# backend/hm_core/billing/api/serializers.py
from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from hm_core.billing.models import BillableEvent, Invoice, InvoiceLine, Payment


class BillableEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillableEvent
        fields = [
            "id",
            "tenant_id",
            "facility_id",
            "encounter",
            "event_type",
            "chargeable_code",
            "quantity",
            "source_order_item",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class InvoiceLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceLine
        fields = [
            "id",
            "tenant_id",
            "facility_id",
            "invoice",
            "billable_event",
            "chargeable_code",
            "description",
            "quantity",
            "unit_price",
            "line_total",
            "tax_percent",
            "tax_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class InvoiceLineCreateSerializer(serializers.Serializer):
    """
    Manual line creation.

    Notes:
    - unit_price is interpreted as:
        * base price if price_includes_tax=false
        * gross (tax-included) price if price_includes_tax=true
    - If tax_percent is omitted and chargeable_code is provided, we try Charge Master.
    """
    description = serializers.CharField(max_length=255)
    chargeable_code = serializers.CharField(required=False, allow_blank=True, default="")
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_percent = serializers.DecimalField(required=False, max_digits=5, decimal_places=2, allow_null=True)
    price_includes_tax = serializers.BooleanField(required=False, default=None)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "tenant_id",
            "facility_id",
            "invoice",
            "amount",
            "method",
            "reference",
            "received_at",
            "recorded_by_user_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    lines = InvoiceLineSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "tenant_id",
            "facility_id",
            "patient",
            "encounter",
            "invoice_number",
            "status",
            "currency",
            "subtotal",
            "discount_total",
            "tax_total",
            "grand_total",
            "amount_paid",
            "balance_due",
            "issued_at",
            "due_at",
            "paid_at",
            "voided_at",
            "notes",
            "lines",
            "payments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class InvoiceCreateSerializer(serializers.Serializer):
    patient = serializers.UUIDField()
    encounter = serializers.UUIDField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class InvoiceGenerateFromEventsSerializer(serializers.Serializer):
    encounter = serializers.UUIDField(required=False, allow_null=True)
    patient = serializers.UUIDField(required=False, allow_null=True)
    default_unit_price = serializers.DecimalField(required=False, max_digits=12, decimal_places=2, default="0.00")


class PaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    method = serializers.CharField(required=False, default="CASH")
    reference = serializers.CharField(required=False, allow_blank=True, default="")
