# backend/hm_core/billing/tests/test_invoice_services.py
from decimal import Decimal

import pytest

from hm_core.billing.models import BillableEvent, InvoiceStatus
from hm_core.billing.services import InvoiceService, PaymentService
from hm_core.orders.models import Order, OrderItem, OrderPriority, OrderType


@pytest.mark.django_db
def test_invoice_create_generate_issue_and_pay(tenant, facility, patient, encounter):
    inv = InvoiceService.create_draft(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=patient.id,
        encounter_id=encounter.id,
    )
    assert inv.status == InvoiceStatus.DRAFT

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

    created = InvoiceService.generate_from_billable_events(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        encounter_id=encounter.id,
        default_unit_price=Decimal("100.00"),
    )
    assert created == 1

    inv = InvoiceService.issue(tenant_id=tenant.id, facility_id=facility.id, invoice_id=inv.id)
    assert inv.status == InvoiceStatus.ISSUED
    assert inv.invoice_number

    # total: 2 * 100 = 200
    assert inv.grand_total == Decimal("200.00")
    assert inv.balance_due == Decimal("200.00")

    pay1 = PaymentService.record_payment(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        amount=Decimal("50.00"),
        method="UPI",
        recorded_by_user_id=None,
    )
    assert pay1.amount == Decimal("50.00")

    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PARTIALLY_PAID
    assert inv.amount_paid == Decimal("50.00")
    assert inv.balance_due == Decimal("150.00")

    pay2 = PaymentService.record_payment(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        amount=Decimal("150.00"),
        method="CASH",
        recorded_by_user_id=None,
    )
    assert pay2.amount == Decimal("150.00")

    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PAID
    assert inv.balance_due == Decimal("0.00")
    assert inv.paid_at is not None

    # event is linked to invoice line and should be billed once
    ev.refresh_from_db()
    assert ev.invoice_line is not None
