# backend/hm_core/billing/services.py
from __future__ import annotations

import re
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from hm_core.billing.models import (
    BillableEvent,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Payment,
    PaymentMethod,
)


class InvoiceService:
    @staticmethod
    @transaction.atomic
    def create_draft(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        patient_id: UUID,
        encounter_id: UUID | None = None,
        notes: str = "",
    ) -> Invoice:
        inv = Invoice.objects.create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            status=InvoiceStatus.DRAFT,
            notes=notes or "",
            subtotal=Decimal("0.00"),
            discount_total=Decimal("0.00"),
            tax_total=Decimal("0.00"),
            grand_total=Decimal("0.00"),
            amount_paid=Decimal("0.00"),
            balance_due=Decimal("0.00"),
        )
        return inv

    @staticmethod
    def _ensure_editable(invoice: Invoice) -> None:
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValidationError({"invoice": "Invoice is not editable unless in DRAFT status."})

    @staticmethod
    def _recalc_totals(invoice: Invoice) -> None:
        lines = InvoiceLine.objects.filter(
            tenant_id=invoice.tenant_id,
            facility_id=invoice.facility_id,
            invoice=invoice,
        )

        subtotal = sum((l.line_total for l in lines), Decimal("0.00"))
        tax_total = sum((l.tax_amount for l in lines), Decimal("0.00"))

        discount_total = invoice.discount_total or Decimal("0.00")
        grand_total = subtotal - discount_total + tax_total

        invoice.subtotal = subtotal.quantize(Decimal("0.01"))
        invoice.tax_total = tax_total.quantize(Decimal("0.01"))
        invoice.grand_total = grand_total.quantize(Decimal("0.01"))
        invoice.balance_due = (invoice.grand_total - (invoice.amount_paid or Decimal("0.00"))).quantize(Decimal("0.01"))

        invoice.save(update_fields=["subtotal", "tax_total", "grand_total", "balance_due", "updated_at"])

    @staticmethod
    @transaction.atomic
    def add_line(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        invoice_id: UUID,
        description: str,
        chargeable_code: str = "",
        quantity: Decimal = Decimal("1.00"),
        unit_price: Decimal = Decimal("0.00"),
        tax_percent: Decimal = Decimal("0.00"),
        billable_event_id: UUID | None = None,
        line_total_override: Decimal | None = None,
        tax_amount_override: Decimal | None = None,
    ) -> InvoiceLine:
        """
        Creates an invoice line and recalculates invoice totals.

        Overrides:
        - line_total_override: set line_total explicitly (useful for inclusive-tax calculations)
        - tax_amount_override: set tax_amount explicitly (useful for inclusive-tax calculations)

        If overrides are not provided, line_total and tax_amount are computed normally.
        """
        invoice = Invoice.objects.select_for_update().get(id=invoice_id, tenant_id=tenant_id, facility_id=facility_id)
        InvoiceService._ensure_editable(invoice)

        if quantity <= 0:
            raise ValidationError({"quantity": "Quantity must be > 0."})
        if unit_price < 0:
            raise ValidationError({"unit_price": "Unit price must be >= 0."})

        tax_percent = Decimal(str(tax_percent)).quantize(Decimal("0.01"))
        if tax_percent < 0:
            raise ValidationError({"tax_percent": "Tax percent must be >= 0."})

        be = None
        if billable_event_id:
            be = BillableEvent.objects.get(id=billable_event_id, tenant_id=tenant_id, facility_id=facility_id)

        computed_line_total = (quantity * unit_price).quantize(Decimal("0.01"))
        line_total = (Decimal(str(line_total_override)).quantize(Decimal("0.01"))
                      if line_total_override is not None else computed_line_total)

        computed_tax_amount = (line_total * tax_percent / Decimal("100.00")).quantize(Decimal("0.01"))
        tax_amount = (Decimal(str(tax_amount_override)).quantize(Decimal("0.01"))
                      if tax_amount_override is not None else computed_tax_amount)

        if line_total < 0:
            raise ValidationError({"line_total": "Line total must be >= 0."})
        if tax_amount < 0:
            raise ValidationError({"tax_amount": "Tax amount must be >= 0."})

        line = InvoiceLine.objects.create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            invoice=invoice,
            billable_event=be,
            chargeable_code=chargeable_code or (be.chargeable_code if be else ""),
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
            tax_percent=tax_percent,
            tax_amount=tax_amount,
        )

        InvoiceService._recalc_totals(invoice)
        return line

    @staticmethod
    @transaction.atomic
    def generate_from_billable_events(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        invoice_id: UUID,
        encounter_id: UUID | None = None,
        patient_id: UUID | None = None,
        default_unit_price: Decimal = Decimal("0.00"),
    ) -> int:
        invoice = Invoice.objects.select_for_update().get(id=invoice_id, tenant_id=tenant_id, facility_id=facility_id)
        InvoiceService._ensure_editable(invoice)

        if not encounter_id and not patient_id and not invoice.encounter_id:
            raise ValidationError({"filter": "Provide encounter_id or patient_id, or create invoice with encounter."})

        eff_encounter_id = encounter_id or invoice.encounter_id
        eff_patient_id = patient_id or invoice.patient_id

        qs = BillableEvent.objects.filter(tenant_id=tenant_id, facility_id=facility_id)
        if eff_encounter_id:
            qs = qs.filter(encounter_id=eff_encounter_id)
        else:
            qs = qs.filter(encounter__patient_id=eff_patient_id)

        qs = qs.order_by("created_at")

        created = 0
        for ev in qs:
            if hasattr(ev, "invoice_line") and ev.invoice_line is not None:
                continue

            qty = Decimal(str(ev.quantity)).quantize(Decimal("0.01"))
            unit_price = Decimal(str(default_unit_price)).quantize(Decimal("0.01"))
            line_total = (qty * unit_price).quantize(Decimal("0.01"))

            tax_percent = Decimal("0.00")
            tax_amount = Decimal("0.00")

            InvoiceLine.objects.create(
                tenant_id=tenant_id,
                facility_id=facility_id,
                invoice=invoice,
                billable_event=ev,
                chargeable_code=ev.chargeable_code,
                description=f"{ev.chargeable_code}",
                quantity=qty,
                unit_price=unit_price,
                line_total=line_total,
                tax_percent=tax_percent,
                tax_amount=tax_amount,
            )
            created += 1

        InvoiceService._recalc_totals(invoice)
        return created

    @staticmethod
    def _next_invoice_number_locked(*, tenant_id: UUID, facility_id: UUID) -> str:
        latest = (
            Invoice.objects.select_for_update()
            .filter(tenant_id=tenant_id, facility_id=facility_id)
            .exclude(invoice_number="")
            .order_by("-created_at")
            .first()
        )

        if not latest or not latest.invoice_number:
            return "INV-000001"

        m = re.match(r"INV-(\d{6})$", latest.invoice_number.strip())
        if not m:
            return f"INV-{timezone.now().strftime('%y%m%d%H%M%S')}"

        n = int(m.group(1)) + 1
        return f"INV-{n:06d}"

    @staticmethod
    @transaction.atomic
    def issue(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        invoice_id: UUID,
        due_at=None,
    ) -> Invoice:
        invoice = Invoice.objects.select_for_update().get(id=invoice_id, tenant_id=tenant_id, facility_id=facility_id)
        InvoiceService._ensure_editable(invoice)

        has_lines = InvoiceLine.objects.filter(
            tenant_id=tenant_id, facility_id=facility_id, invoice=invoice
        ).exists()
        if not has_lines:
            raise ValidationError({"invoice": "Cannot issue an empty invoice."})

        if not invoice.invoice_number:
            invoice.invoice_number = InvoiceService._next_invoice_number_locked(
                tenant_id=tenant_id, facility_id=facility_id
            )

        invoice.status = InvoiceStatus.ISSUED
        invoice.issued_at = timezone.now()
        if due_at is not None:
            invoice.due_at = due_at

        InvoiceService._recalc_totals(invoice)

        invoice.save(update_fields=["invoice_number", "status", "issued_at", "due_at", "updated_at"])
        return invoice

    @staticmethod
    @transaction.atomic
    def void(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        invoice_id: UUID,
        reason: str = "",
    ) -> Invoice:
        invoice = Invoice.objects.select_for_update().get(id=invoice_id, tenant_id=tenant_id, facility_id=facility_id)

        if invoice.status == InvoiceStatus.PAID:
            raise ValidationError({"invoice": "Cannot void a PAID invoice. Use a reversal/credit flow."})

        invoice.mark_void()
        if reason:
            invoice.notes = (invoice.notes + "\n" + f"VOID: {reason}").strip()

        invoice.save(update_fields=["status", "voided_at", "notes", "updated_at"])
        return invoice


class PaymentService:
    @staticmethod
    @transaction.atomic
    def record_payment(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        invoice_id: UUID,
        amount: Decimal,
        method: str = PaymentMethod.CASH,
        reference: str = "",
        recorded_by_user_id: int | None = None,
    ) -> Payment:
        invoice = Invoice.objects.select_for_update().get(id=invoice_id, tenant_id=tenant_id, facility_id=facility_id)

        if invoice.status == InvoiceStatus.VOID:
            raise ValidationError({"invoice": "Cannot record payment for a VOID invoice."})

        if amount <= 0:
            raise ValidationError({"amount": "Payment amount must be > 0."})

        pay = Payment.objects.create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            invoice=invoice,
            amount=amount.quantize(Decimal("0.01")),
            method=method,
            reference=reference or "",
            recorded_by_user_id=recorded_by_user_id,
        )

        invoice.amount_paid = (invoice.amount_paid or Decimal("0.00")) + pay.amount
        invoice.balance_due = (invoice.grand_total or Decimal("0.00")) - invoice.amount_paid

        if invoice.balance_due <= Decimal("0.00"):
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = timezone.now()
            invoice.balance_due = Decimal("0.00")
        elif invoice.status in [InvoiceStatus.ISSUED, InvoiceStatus.DRAFT]:
            invoice.status = InvoiceStatus.PARTIALLY_PAID

        invoice.save(update_fields=["status", "amount_paid", "balance_due", "paid_at", "updated_at"])
        return pay
