# backend/hm_core/billing/tests/test_payment_workflow.py
from decimal import Decimal

import pytest
from rest_framework.exceptions import ValidationError

from hm_core.billing.models import InvoiceStatus
from hm_core.billing.services import InvoiceService, PaymentService


@pytest.mark.django_db
def test_payment_partial_then_full_transitions_status(tenant, facility, patient, encounter):
    inv = InvoiceService.create_draft(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=patient.id,
        encounter_id=encounter.id,
    )

    # Add a line and issue so totals are set
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
    assert inv.grand_total == Decimal("500.00")

    # Partial payment
    pay1 = PaymentService.record_payment(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        amount=Decimal("200.00"),
        method="UPI",
        reference="UTR-001",
        recorded_by_user_id=None,
    )
    assert pay1.amount == Decimal("200.00")

    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PARTIALLY_PAID
    assert inv.amount_paid == Decimal("200.00")
    assert inv.balance_due == Decimal("300.00")

    # Remaining payment
    pay2 = PaymentService.record_payment(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        amount=Decimal("300.00"),
        method="CASH",
        reference="",
        recorded_by_user_id=None,
    )
    assert pay2.amount == Decimal("300.00")

    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PAID
    assert inv.amount_paid == Decimal("500.00")
    assert inv.balance_due == Decimal("0.00")
    assert inv.paid_at is not None


@pytest.mark.django_db
def test_payment_negative_or_zero_amount_rejected(tenant, facility, patient, encounter):
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
        description="Registration",
        chargeable_code="reg",
        quantity=Decimal("1.00"),
        unit_price=Decimal("100.00"),
    )
    inv = InvoiceService.issue(tenant_id=tenant.id, facility_id=facility.id, invoice_id=inv.id)

    with pytest.raises(ValidationError):
        PaymentService.record_payment(
            tenant_id=tenant.id,
            facility_id=facility.id,
            invoice_id=inv.id,
            amount=Decimal("0.00"),
            method="CASH",
            reference="",
            recorded_by_user_id=None,
        )

    with pytest.raises(ValidationError):
        PaymentService.record_payment(
            tenant_id=tenant.id,
            facility_id=facility.id,
            invoice_id=inv.id,
            amount=Decimal("-1.00"),
            method="CASH",
            reference="",
            recorded_by_user_id=None,
        )


@pytest.mark.django_db
def test_payment_not_allowed_on_void_invoice(tenant, facility, patient, encounter):
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

    inv = InvoiceService.void(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        reason="cancelled",
    )
    assert inv.status == InvoiceStatus.VOID

    with pytest.raises(ValidationError):
        PaymentService.record_payment(
            tenant_id=tenant.id,
            facility_id=facility.id,
            invoice_id=inv.id,
            amount=Decimal("10.00"),
            method="CASH",
            reference="",
            recorded_by_user_id=None,
        )


@pytest.mark.django_db
def test_overpayment_clamps_balance_and_marks_paid(tenant, facility, patient, encounter):
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
        description="Registration",
        chargeable_code="reg",
        quantity=Decimal("1.00"),
        unit_price=Decimal("100.00"),
    )
    inv = InvoiceService.issue(tenant_id=tenant.id, facility_id=facility.id, invoice_id=inv.id)

    PaymentService.record_payment(
        tenant_id=tenant.id,
        facility_id=facility.id,
        invoice_id=inv.id,
        amount=Decimal("150.00"),  # overpay
        method="CASH",
        reference="",
        recorded_by_user_id=None,
    )

    inv.refresh_from_db()
    assert inv.status == InvoiceStatus.PAID
    assert inv.balance_due == Decimal("0.00")
