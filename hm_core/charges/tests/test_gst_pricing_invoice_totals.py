# backend/hm_core/charges/tests/test_gst_pricing_invoice_totals.py
from decimal import Decimal

import pytest

from hm_core.billing.models import BillableEvent, Invoice, InvoiceLine, InvoiceStatus
from hm_core.charges.services import ChargeItemService
from hm_core.orders.models import Order, OrderItem, OrderPriority, OrderType

pytestmark = pytest.mark.django_db


def test_billable_event_auto_prices_line_and_applies_gst_and_updates_invoice_totals(
    tenant, facility, patient, encounter
):
    # Charge master: CBC = 250.00 with 18% GST
    ChargeItemService.upsert(
        tenant_id=tenant.id,
        facility_id=facility.id,
        code="cbc",
        name="Complete Blood Count",
        default_price=Decimal("250.00"),
        tax_percent=Decimal("18.00"),
        department="LAB",
        is_active=True,
    )

    # Create order + item to satisfy BillableEvent.source_order_item OneToOne
    order = Order.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter=encounter,
        order_type=OrderType.LAB,
    )
    item = OrderItem.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        order=order,
        encounter=encounter,
        service_code="cbc",
        priority=OrderPriority.ROUTINE,
    )

    # Creating BillableEvent triggers billing signal -> draft invoice + invoice line
    ev = BillableEvent.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter=encounter,
        source_order_item=item,
        chargeable_code="cbc",
        quantity=2,
    )

    inv = Invoice.objects.get(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        status=InvoiceStatus.DRAFT,
    )
    assert inv.patient_id == patient.id

    line = InvoiceLine.objects.get(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice=inv,
        billable_event=ev,
    )

    # Qty=2, Unit=250 => line_total=500
    assert line.description == "Complete Blood Count"
    assert line.quantity == Decimal("2.00")
    assert line.unit_price == Decimal("250.00")
    assert line.line_total == Decimal("500.00")

    # GST 18% on 500 => 90
    assert line.tax_percent == Decimal("18.00")
    assert line.tax_amount == Decimal("90.00")

    inv.refresh_from_db()

    # Invoice totals:
    # subtotal = 500
    # tax_total = 90
    # discount_total default = 0
    # grand_total = 590
    # balance_due = 590 (since no payment)
    assert inv.subtotal == Decimal("500.00")
    assert inv.tax_total == Decimal("90.00")
    assert inv.discount_total == Decimal("0.00")
    assert inv.grand_total == Decimal("590.00")
    assert inv.amount_paid == Decimal("0.00")
    assert inv.balance_due == Decimal("590.00")


def test_billable_event_fallback_when_no_charge_item_sets_zero_price_and_zero_tax(
    tenant, facility, patient, encounter
):
    order = Order.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter=encounter,
        order_type=OrderType.LAB,
    )
    item = OrderItem.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        order=order,
        encounter=encounter,
        service_code="unknown",
        priority=OrderPriority.ROUTINE,
    )

    ev = BillableEvent.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter=encounter,
        source_order_item=item,
        chargeable_code="unknown",
        quantity=1,
    )

    inv = Invoice.objects.get(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        status=InvoiceStatus.DRAFT,
    )

    line = InvoiceLine.objects.get(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice=inv,
        billable_event=ev,
    )

    assert line.description == "unknown"
    assert line.unit_price == Decimal("0.00")
    assert line.line_total == Decimal("0.00")
    assert line.tax_percent == Decimal("0.00")
    assert line.tax_amount == Decimal("0.00")

    inv.refresh_from_db()
    assert inv.subtotal == Decimal("0.00")
    assert inv.tax_total == Decimal("0.00")
    assert inv.grand_total == Decimal("0.00")
    assert inv.balance_due == Decimal("0.00")
