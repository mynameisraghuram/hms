import pytest

from hm_core.billing.models import BillableEvent, Invoice, InvoiceLine, InvoiceStatus
from hm_core.charges.services import ChargeItemService
from hm_core.orders.models import Order, OrderItem, OrderPriority, OrderType

pytestmark = pytest.mark.django_db


def test_billable_event_creates_priced_invoice_line_when_charge_item_exists(tenant, facility, patient, encounter):
    # Create a price in charge master
    ChargeItemService.upsert(
        tenant_id=tenant.id,
        facility_id=facility.id,
        code="cbc",
        name="Complete Blood Count",
        default_price="250.00",
        tax_percent="0.00",
        department="LAB",
        is_active=True,
    )

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

    line = InvoiceLine.objects.get(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice=inv,
        billable_event=ev,
    )

    assert line.description == "Complete Blood Count"
    assert str(line.unit_price) == "250.00"
    assert str(line.line_total) == "500.00"

    inv.refresh_from_db()
    # Invoice totals are recalculated by signal
    assert str(inv.grand_total) == "500.00"
    assert str(inv.balance_due) == "500.00"
