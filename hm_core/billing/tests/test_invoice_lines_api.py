# backend/hm_core/billing/tests/test_invoice_lines_api.py
from decimal import Decimal

import pytest

from hm_core.charges.services import ChargeItemService
from hm_core.facilities.models import PricingTaxMode

pytestmark = pytest.mark.django_db


def _scope_headers(tenant, facility):
    return {
        "HTTP_X_TENANT_ID": str(tenant.id),
        "HTTP_X_FACILITY_ID": str(facility.id),
    }


def _create_draft_invoice(api_client, tenant, facility, patient, encounter):
    url = "/api/v1/billing/invoices/"
    payload = {
        "patient": str(patient.id),
        "encounter": str(encounter.id),
        "notes": "draft for tests",
    }
    res = api_client.post(url, payload, format="json", **_scope_headers(tenant, facility))
    assert res.status_code == 201, res.data
    return res.data


def test_invoice_lines_post_exclusive_tax_added_on_top(api_client, tenant, facility, patient, encounter):
    facility.pricing_tax_mode = PricingTaxMode.EXCLUSIVE
    facility.save(update_fields=["pricing_tax_mode", "updated_at"])

    ChargeItemService.upsert(
        tenant_id=tenant.id,
        facility_id=facility.id,
        code="cons",
        name="Consultation",
        default_price="500.00",
        tax_percent="18.00",
        department="OPD",
        is_active=True,
    )

    inv = _create_draft_invoice(api_client, tenant, facility, patient, encounter)
    invoice_id = inv["id"]

    url = f"/api/v1/billing/invoices/{invoice_id}/lines/"
    payload = {
        "description": "Consultation fee",
        "chargeable_code": "cons",
        "quantity": "1.00",
        "unit_price": "500.00",
        "price_includes_tax": False,
    }

    res = api_client.post(url, payload, format="json", **_scope_headers(tenant, facility))
    assert res.status_code == 201, res.data

    line = res.data
    assert line["chargeable_code"] == "cons"
    assert line["description"] == "Consultation fee"
    assert Decimal(str(line["quantity"])) == Decimal("1.00")
    assert Decimal(str(line["unit_price"])) == Decimal("500.00")
    assert Decimal(str(line["line_total"])) == Decimal("500.00")

    assert Decimal(str(line["tax_percent"])) == Decimal("18.00")
    assert Decimal(str(line["tax_amount"])) == Decimal("90.00")

    inv_get = api_client.get(f"/api/v1/billing/invoices/{invoice_id}/", **_scope_headers(tenant, facility))
    assert inv_get.status_code == 200, inv_get.data

    assert Decimal(str(inv_get.data["subtotal"])) == Decimal("500.00")
    assert Decimal(str(inv_get.data["tax_total"])) == Decimal("90.00")
    assert Decimal(str(inv_get.data["grand_total"])) == Decimal("590.00")
    assert Decimal(str(inv_get.data["balance_due"])) == Decimal("590.00")


def test_invoice_lines_post_inclusive_price_splits_tax(api_client, tenant, facility, patient, encounter):
    facility.pricing_tax_mode = PricingTaxMode.INCLUSIVE
    facility.save(update_fields=["pricing_tax_mode", "updated_at"])

    ChargeItemService.upsert(
        tenant_id=tenant.id,
        facility_id=facility.id,
        code="cbc",
        name="Complete Blood Count",
        default_price="250.00",
        tax_percent="18.00",
        department="LAB",
        is_active=True,
    )

    inv = _create_draft_invoice(api_client, tenant, facility, patient, encounter)
    invoice_id = inv["id"]

    url = f"/api/v1/billing/invoices/{invoice_id}/lines/"
    payload = {
        "description": "CBC Test",
        "chargeable_code": "cbc",
        "quantity": "2.00",
        "unit_price": "250.00",  # gross per unit (includes tax)
        # tax_percent omitted intentionally -> uses charge master
        # price_includes_tax omitted intentionally -> defaults to facility INCLUSIVE
    }

    res = api_client.post(url, payload, format="json", **_scope_headers(tenant, facility))
    assert res.status_code == 201, res.data

    line = res.data
    assert line["chargeable_code"] == "cbc"
    assert line["description"] == "CBC Test"
    assert Decimal(str(line["quantity"])) == Decimal("2.00")

    # gross total 500.00 => base 423.73, tax 76.27
    assert Decimal(str(line["line_total"])) == Decimal("423.73")
    assert Decimal(str(line["tax_percent"])) == Decimal("18.00")
    assert Decimal(str(line["tax_amount"])) == Decimal("76.27")

    inv_get = api_client.get(f"/api/v1/billing/invoices/{invoice_id}/", **_scope_headers(tenant, facility))
    assert inv_get.status_code == 200, inv_get.data

    assert Decimal(str(inv_get.data["subtotal"])) == Decimal("423.73")
    assert Decimal(str(inv_get.data["tax_total"])) == Decimal("76.27")
    assert Decimal(str(inv_get.data["grand_total"])) == Decimal("500.00")
    assert Decimal(str(inv_get.data["balance_due"])) == Decimal("500.00")
