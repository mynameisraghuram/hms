# backend/hm_core/charges/tests/test_facility_tax_mode_inclusive_exclusive.py
from decimal import Decimal

import pytest

from hm_core.billing.models import BillableEvent, Invoice, InvoiceLine, InvoiceStatus
from hm_core.charges.services import ChargeItemService
from hm_core.facilities.models import PricingTaxMode
from hm_core.orders.models import Order, OrderItem, OrderPriority, OrderType

pytestmark = pytest.mark.django_db


def _create_order_item(*, tenant, facility, encounter):
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
    return item


def test_tax_mode_exclusive_adds_tax_on_top(tenant, facility, patient, encounter):
    facility.pricing_tax_mode = PricingTaxMode.EXCLUSIVE
    facility.save(update_fields=["pricing_tax_mode", "updated_at"])

    ChargeItemService.upsert(
        tenant_id=tenant.id,
        facility_id=facility.id,
        code="cbc",
        name="Complete Blood Count",
        default_price=Decimal("250.00"),  # base price
        tax_percent=Decimal("18.00"),
        department="LAB",
        is_active=True,
    )

    item = _create_order_item(tenant=tenant, facility=facility, encounter=encounter)

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
    line = InvoiceLine.objects.get(invoice=inv, billable_event=ev)

    # qty 2 * 250 = 500 base, tax 18% = 90, grand = 590
    assert line.unit_price == Decimal("250.00")
    assert line.line_total == Decimal("500.00")
    assert line.tax_percent == Decimal("18.00")
    assert line.tax_amount == Decimal("90.00")

    inv.refresh_from_db()
    assert inv.subtotal == Decimal("500.00")
    assert inv.tax_total == Decimal("90.00")
    assert inv.grand_total == Decimal("590.00")
    assert inv.balance_due == Decimal("590.00")


def test_tax_mode_inclusive_splits_tax_out_of_price(tenant, facility, patient, encounter):
    facility.pricing_tax_mode = PricingTaxMode.INCLUSIVE
    facility.save(update_fields=["pricing_tax_mode", "updated_at"])

    ChargeItemService.upsert(
        tenant_id=tenant.id,
        facility_id=facility.id,
        code="cbc",
        name="Complete Blood Count",
        default_price=Decimal("250.00"),  # gross (includes tax) per unit
        tax_percent=Decimal("18.00"),
        department="LAB",
        is_active=True,
    )

    item = _create_order_item(tenant=tenant, facility=facility, encounter=encounter)

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
    line = InvoiceLine.objects.get(invoice=inv, billable_event=ev)

    # gross total = 2 * 250 = 500
    # base = 500 / 1.18 = 423.73 (rounded)
    # tax = 76.27, grand = 500.00
    assert line.tax_percent == Decimal("18.00")
    assert line.line_total == Decimal("423.73")
    assert line.tax_amount == Decimal("76.27")

    inv.refresh_from_db()
    assert inv.subtotal == Decimal("423.73")
    assert inv.tax_total == Decimal("76.27")
    assert inv.grand_total == Decimal("500.00")
    assert inv.balance_due == Decimal("500.00")
