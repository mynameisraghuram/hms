# backend\hm_core\billing\models.py
from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils import timezone

from hm_core.common.models import ScopedModel
from hm_core.encounters.models import Encounter
from hm_core.orders.models import OrderItem
from hm_core.patients.models import Patient


class EventType(models.TextChoices):
    SERVICE_DELIVERED = "SERVICE_DELIVERED", "Service Delivered"


class BillableEvent(ScopedModel):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="billable_events")
    source_order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name="billable_event")

    event_type = models.CharField(max_length=32, choices=EventType.choices, default=EventType.SERVICE_DELIVERED)
    chargeable_code = models.SlugField(max_length=64)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "billing_billable_event"
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "encounter"]),
        ]


# -------------------------------------------------------------------
# Billing v1: Invoice + Lines + Payments
# -------------------------------------------------------------------

class InvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ISSUED = "ISSUED", "Issued"
    PARTIALLY_PAID = "PARTIALLY_PAID", "Partially Paid"
    PAID = "PAID", "Paid"
    VOID = "VOID", "Void"


class Invoice(ScopedModel):
    """
    Financial document built from billable events (or manual lines).
    Once ISSUED, treat as immutable (enforced in services).
    """
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="invoices")
    encounter = models.ForeignKey(
        Encounter,
        on_delete=models.PROTECT,
        related_name="invoices",
        null=True,
        blank=True,
    )

    invoice_number = models.CharField(max_length=32, blank=True)  # assigned on issue
    status = models.CharField(max_length=32, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT, db_index=True)

    currency = models.CharField(max_length=8, default="INR")

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    balance_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    issued_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    class Meta:
        db_table = "billing_invoice"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "facility_id", "invoice_number"],
                name="uq_invoice_scope_number",
            )
        ]
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "status", "created_at"]),
            models.Index(fields=["tenant_id", "facility_id", "patient", "created_at"]),
            models.Index(fields=["tenant_id", "facility_id", "encounter", "created_at"]),
        ]

    def mark_void(self):
        self.status = InvoiceStatus.VOID
        self.voided_at = timezone.now()


class InvoiceLine(ScopedModel):
    """
    Snapshot line item. Optionally linked to a BillableEvent to enforce 'billed once'.

    Tax:
    - tax_percent: GST% for this line (e.g. 18.00)
    - tax_amount: snapshot amount (line_total * tax_percent / 100)
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")

    billable_event = models.OneToOneField(
        BillableEvent,
        on_delete=models.SET_NULL,
        related_name="invoice_line",
        null=True,
        blank=True,
    )

    chargeable_code = models.SlugField(max_length=64, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "billing_invoice_line"
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "invoice"]),
        ]


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    CARD = "CARD", "Card"
    UPI = "UPI", "UPI"
    BANK = "BANK", "Bank Transfer"
    INSURANCE = "INSURANCE", "Insurance"
    OTHER = "OTHER", "Other"


class Payment(ScopedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=32, choices=PaymentMethod.choices, default=PaymentMethod.CASH)

    reference = models.CharField(max_length=64, blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    recorded_by_user_id = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "billing_payment"
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "invoice", "received_at"]),
        ]
