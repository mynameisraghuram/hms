# backend/hm_core/billing/tests/test_auto_invoice_from_billable_event.py

from decimal import Decimal

import pytest

from hm_core.billing.models import BillableEvent, Invoice, InvoiceLine, InvoiceStatus
from hm_core.orders.models import Order, OrderItem, OrderPriority, OrderType


pytestmark = pytest.mark.django_db


def test_billable_event_auto_creates_draft_invoice_and_line(tenant, facility, patient, encounter):
    # Create an order item to satisfy BillableEvent.source_order_item (OneToOne)
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

    # Create billable event -> signal should create invoice + line
    ev = BillableEvent.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter=encounter,
        source_order_item=item,
        chargeable_code="cbc",
        quantity=2,
    )

    inv_qs = Invoice.objects.filter(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        status=InvoiceStatus.DRAFT,
    )
    assert inv_qs.count() == 1

    inv = inv_qs.first()
    assert inv.patient_id == patient.id

    line_qs = InvoiceLine.objects.filter(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice=inv,
        billable_event=ev,
    )
    assert line_qs.count() == 1

    line = line_qs.first()
    assert line.chargeable_code == "cbc"
    assert line.quantity == Decimal("2.00")

    # Pricing is not implemented yet; line_total stays 0.00
    assert line.unit_price == Decimal("0.00")
    assert line.line_total == Decimal("0.00")
