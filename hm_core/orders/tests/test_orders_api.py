# backend/hm_core/orders/tests/test_orders_api.py
import pytest
from hm_core.tests.helpers import scoped

pytestmark = pytest.mark.django_db


def test_create_lab_order_creates_order_and_items(api_client, tenant, facility, encounter):
    url = "/api/v1/orders/"
    payload = {
        "encounter_id": str(encounter.id),
        "order_type": "LAB",
        "priority": "ROUTINE",
        "items": [
            {"service_code": "CBC"},
            {"service_code": "LIPID_PROFILE"},
        ],
    }

    r = api_client.post(url, payload, format="json", **scoped(tenant, facility))
    assert r.status_code in (200, 201), r.data
    assert "id" in r.data
    assert "items" in r.data
    assert len(r.data["items"]) == 2


def test_create_lab_order_requires_scope_headers(api_client, encounter):
    url = "/api/v1/orders/"
    payload = {
        "encounter_id": str(encounter.id),
        "order_type": "LAB",
        "priority": "ROUTINE",
        "items": [{"service_code": "CBC"}],
    }

    r = api_client.post(url, payload, format="json")
    assert r.status_code in (400, 403), r.data


def test_create_lab_order_idempotent_double_post_no_duplicates(api_client, tenant, facility, encounter):
    """
    Assumes idempotency via HTTP_IDEMPOTENCY_KEY.
    If not implemented yet, keep the test and make it pass in Phase-1.
    """
    url = "/api/v1/orders/"
    payload = {
        "encounter_id": str(encounter.id),
        "order_type": "LAB",
        "priority": "ROUTINE",
        "items": [{"service_code": "CBC"}],
    }

    headers = scoped(tenant, facility)
    headers["HTTP_IDEMPOTENCY_KEY"] = "order-001"

    r1 = api_client.post(url, payload, format="json", **headers)
    r2 = api_client.post(url, payload, format="json", **headers)

    assert r1.status_code in (200, 201), r1.data
    assert r2.status_code in (200, 201), r2.data
    assert r1.data["id"] == r2.data["id"]
