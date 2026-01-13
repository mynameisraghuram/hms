# backend/hm_core/billing/tests/test_invoice_api.py
from decimal import Decimal

import pytest

from hm_core.conftest import scope_headers
from hm_core.billing.models import BillableEvent
from hm_core.orders.models import Order, OrderItem, OrderPriority, OrderType


@pytest.mark.django_db
def test_invoice_api_create_generate_issue_and_pay(api_client, tenant, facility, patient, encounter):
    headers = scope_headers(tenant, facility)

    # create draft invoice
    resp = api_client.post(
        "/api/v1/billing/invoices/",
        {"patient": str(patient.id), "encounter": str(encounter.id), "notes": "Test invoice"},
        format="json",
        **headers,
    )
    assert resp.status_code == 201
    inv_id = resp.data["id"]

    # create billable event
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
        service_code="xray",
        priority=OrderPriority.ROUTINE,
    )
    BillableEvent.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter=encounter,
        source_order_item=item,
        chargeable_code="xray",
        quantity=1,
    )

    # generate lines from events
    resp = api_client.post(
        f"/api/v1/billing/invoices/{inv_id}/generate_from_events/",
        {"encounter": str(encounter.id), "default_unit_price": "250.00"},
        format="json",
        **headers,
    )
    assert resp.status_code == 200
    assert resp.data["created_lines"] == 1

    # issue
    resp = api_client.post(f"/api/v1/billing/invoices/{inv_id}/issue/", {}, format="json", **headers)
    assert resp.status_code == 200
    assert resp.data["status"] in ["ISSUED", "PARTIALLY_PAID", "PAID"]
    assert resp.data["invoice_number"]

    # pay
    resp = api_client.post(
        f"/api/v1/billing/invoices/{inv_id}/payments/",
        {"amount": str(Decimal("250.00")), "method": "UPI", "reference": "UTR123"},
        format="json",
        **headers,
    )
    assert resp.status_code == 201
    assert resp.data["amount"] == "250.00"

    # invoice should be paid now
    resp = api_client.get(f"/api/v1/billing/invoices/{inv_id}/", **headers)
    assert resp.status_code == 200
    assert resp.data["status"] == "PAID"
    assert resp.data["balance_due"] == "0.00"
