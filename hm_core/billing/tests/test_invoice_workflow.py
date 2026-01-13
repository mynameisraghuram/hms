# backend/hm_core/billing/tests/test_invoice_workflow.py
from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError

from hm_core.billing.models import BillableEvent, InvoiceLine, InvoiceStatus
from hm_core.billing.services import InvoiceService
from hm_core.orders.models import Order, OrderItem, OrderPriority, OrderType


@pytest.mark.django_db
def test_invoice_draft_allows_manual_lines_and_recalc(tenant, facility, patient, encounter):
    inv = InvoiceService.create_draft(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=patient.id,
        encounter_id=encounter.id,
        notes="draft ok",
    )
    assert inv.status == InvoiceStatus.DRAFT
    assert inv.grand_total == Decimal("0.00")
    assert inv.balance_due == Decimal("0.00")

    # Add two manual lines
    line1 = InvoiceService.add_line(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        description="Consultation",
        chargeable_code="consult",
        quantity=Decimal("1.00"),
        unit_price=Decimal("500.00"),
    )
    assert line1.line_total == Decimal("500.00")

    line2 = InvoiceService.add_line(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        description="Registration",
        chargeable_code="reg",
        quantity=Decimal("1.00"),
        unit_price=Decimal("100.00"),
    )
    assert line2.line_total == Decimal("100.00")

    inv.refresh_from_db()
    assert inv.subtotal == Decimal("600.00")
    assert inv.grand_total == Decimal("600.00")
    assert inv.balance_due == Decimal("600.00")
    assert InvoiceLine.objects.filter(invoice=inv).count() == 2


@pytest.mark.django_db
def test_generate_from_billable_events_is_idempotent_and_skips_already_billed(tenant, facility, patient, encounter):
    inv = InvoiceService.create_draft(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=patient.id,
        encounter_id=encounter.id,
    )

    # Create an order + item + billable event (typical lab delivered scenario)
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
        quantity=1,
    )

    # First generation -> creates 1 line
    created1 = InvoiceService.generate_from_billable_events(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        encounter_id=encounter.id,
        default_unit_price=Decimal("250.00"),
    )
    assert created1 == 1

    inv.refresh_from_db()
    assert inv.grand_total == Decimal("250.00")

    # Second generation -> should skip because already linked via OneToOne
    created2 = InvoiceService.generate_from_billable_events(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        encounter_id=encounter.id,
        default_unit_price=Decimal("250.00"),
    )
    assert created2 == 0

    # Verify the event is linked to exactly one invoice line
    ev.refresh_from_db()
    assert ev.invoice_line is not None
    assert InvoiceLine.objects.filter(invoice=inv).count() == 1


@pytest.mark.django_db
def test_issue_requires_lines_and_assigns_invoice_number(tenant, facility, patient, encounter):
    inv = InvoiceService.create_draft(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=patient.id,
        encounter_id=encounter.id,
    )

    # Cannot issue empty invoice
    with pytest.raises(ValidationError):
        InvoiceService.issue(
            tenant_id=tenant.id,
            facility_id=facility.id,
            invoice_id=inv.id,
        )

    # Add a line and issue
    InvoiceService.add_line(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        description="Consultation",
        chargeable_code="consult",
        quantity=Decimal("1.00"),
        unit_price=Decimal("500.00"),
    )

    inv = InvoiceService.issue(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
    )
    assert inv.status == InvoiceStatus.ISSUED
    assert inv.invoice_number  # assigned on issue
    assert inv.issued_at is not None
    assert inv.grand_total == Decimal("500.00")
    assert inv.balance_due == Decimal("500.00")


@pytest.mark.django_db
def test_issue_locks_editing_add_line_after_issue_fails(tenant, facility, patient, encounter):
    inv = InvoiceService.create_draft(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=patient.id,
        encounter_id=encounter.id,
    )

    InvoiceService.add_line(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        description="Consultation",
        chargeable_code="consult",
        quantity=Decimal("1.00"),
        unit_price=Decimal("500.00"),
    )

    inv = InvoiceService.issue(tenant_id=tenant.id, facility_id=facility.id, invoice_id=inv.id)
    assert inv.status == InvoiceStatus.ISSUED

    # Editing should be blocked after issue
    with pytest.raises(ValidationError):
        InvoiceService.add_line(
            tenant_id=tenant.id,
            facility_id=facility.id,
            invoice_id=inv.id,
            description="Late fee",
            chargeable_code="late",
            quantity=Decimal("1.00"),
            unit_price=Decimal("10.00"),
        )


@pytest.mark.django_db
def test_void_draft_or_issued_ok_void_paid_not_allowed(tenant, facility, patient, encounter):
    inv = InvoiceService.create_draft(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=patient.id,
        encounter_id=encounter.id,
    )

    # void draft should work
    inv = InvoiceService.void(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        reason="mistake",
    )
    assert inv.status == InvoiceStatus.VOID
    assert inv.voided_at is not None
    assert "VOID:" in inv.notes
