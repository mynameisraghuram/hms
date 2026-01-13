# backend/hm_core/billing/signals/billable_event_to_invoice.py
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from hm_core.billing.models import BillableEvent, Invoice, InvoiceLine, InvoiceStatus
from hm_core.billing.services import InvoiceService
from hm_core.charges.selectors import get_active_charge_item
from hm_core.facilities.models import Facility, PricingTaxMode


@receiver(post_save, sender=BillableEvent)
def auto_attach_billable_event_to_invoice(sender, instance: BillableEvent, created: bool, **kwargs):
    """
    Auto-billing behavior:

    - If a DRAFT invoice already exists for this encounter:
        ✅ Do NOT create invoice lines here.
        (Lines will be created by InvoiceService.generate_from_billable_events)

    - If no DRAFT invoice exists yet:
        ✅ Create a DRAFT invoice + one InvoiceLine for this BillableEvent.
        (Supports "fire-and-forget" auto billing flows)

    This keeps both workflows compatible and tests consistent.
    """
    if not created:
        return

    encounter = instance.encounter
    if not encounter or not getattr(encounter, "patient_id", None):
        return

    tenant_id = instance.tenant_id
    facility_id = instance.facility_id

    with transaction.atomic():
        # If an invoice already exists (created manually / via API), DO NOT create lines here.
        existing = (
            Invoice.objects.select_for_update()
            .filter(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=encounter.id,
                status=InvoiceStatus.DRAFT,
            )
            .first()
        )
        if existing:
            # keep patient in sync (defensive)
            if existing.patient_id != encounter.patient_id:
                existing.patient_id = encounter.patient_id
                existing.save(update_fields=["patient_id", "updated_at"])
            return

        # Otherwise create the invoice + the single line for this event.
        invoice = Invoice.objects.create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter.id,
            patient_id=encounter.patient_id,
            status=InvoiceStatus.DRAFT,
            currency="INR",
            subtotal=Decimal("0.00"),
            discount_total=Decimal("0.00"),
            tax_total=Decimal("0.00"),
            grand_total=Decimal("0.00"),
            amount_paid=Decimal("0.00"),
            balance_due=Decimal("0.00"),
            notes="",
        )

        qty = Decimal(str(instance.quantity)).quantize(Decimal("0.01"))

        facility = (
            Facility.objects.filter(tenant_id=tenant_id, id=facility_id)
            .only("pricing_tax_mode")
            .first()
        )
        pricing_tax_mode = facility.pricing_tax_mode if facility else PricingTaxMode.EXCLUSIVE

        charge = get_active_charge_item(
            tenant_id=tenant_id,
            facility_id=facility_id,
            code=instance.chargeable_code,
        )

        if charge:
            list_unit_price = Decimal(str(charge.default_price)).quantize(Decimal("0.01"))
            tax_percent = Decimal(str(charge.tax_percent)).quantize(Decimal("0.01"))
            description = (charge.name or str(instance.chargeable_code))[:255]
        else:
            list_unit_price = Decimal("0.00")
            tax_percent = Decimal("0.00")
            description = str(instance.chargeable_code)[:255]

        if pricing_tax_mode == PricingTaxMode.INCLUSIVE and tax_percent > Decimal("0.00"):
            gross_line_total = (qty * list_unit_price).quantize(Decimal("0.01"))
            divisor = (Decimal("1.00") + (tax_percent / Decimal("100.00")))
            base_line_total = (gross_line_total / divisor).quantize(Decimal("0.01"))
            tax_amount = (gross_line_total - base_line_total).quantize(Decimal("0.01"))
            unit_price = (base_line_total / qty).quantize(Decimal("0.01")) if qty > 0 else Decimal("0.00")
            line_total = base_line_total
        else:
            unit_price = list_unit_price
            line_total = (qty * unit_price).quantize(Decimal("0.01"))
            tax_amount = (line_total * tax_percent / Decimal("100.00")).quantize(Decimal("0.01"))

        InvoiceLine.objects.get_or_create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            billable_event=instance,
            defaults={
                "invoice": invoice,
                "chargeable_code": instance.chargeable_code,
                "description": description,
                "quantity": qty,
                "unit_price": unit_price,
                "line_total": line_total,
                "tax_percent": tax_percent,
                "tax_amount": tax_amount,
            },
        )

        InvoiceService._recalc_totals(invoice)
