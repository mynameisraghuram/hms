import pytest
from hm_core.tests.helpers import scoped

pytestmark = pytest.mark.django_db


def _create_order_and_get_item(api_client, tenant, facility, encounter):
    r = api_client.post(
        "/api/v1/orders/",
        {
            "encounter_id": str(encounter.id),
            "order_type": "LAB",
            "priority": "ROUTINE",
            "items": [{"service_code": "CBC"}],
        },
        format="json",
        **scoped(tenant, facility),
    )
    assert r.status_code in (200, 201), r.data
    return r.data["items"][0]["id"]


def test_sample_receive_creates_or_updates_sample(api_client, tenant, facility, encounter):
    order_item_id = _create_order_and_get_item(api_client, tenant, facility, encounter)

    r = api_client.post(
        "/api/v1/lab/samples/receive/",
        {"order_item_id": str(order_item_id), "barcode": "SAMPLE-001"},
        format="json",
        **scoped(tenant, facility),
    )
    assert r.status_code in (200, 201), r.data
    assert str(r.data.get("order_item_id")) == str(order_item_id)


def test_sample_receive_idempotent_double_post(api_client, tenant, facility, encounter):
    order_item_id = _create_order_and_get_item(api_client, tenant, facility, encounter)

    headers = scoped(tenant, facility)
    headers["HTTP_IDEMPOTENCY_KEY"] = "sample-receive-001"

    r1 = api_client.post(
        "/api/v1/lab/samples/receive/",
        {"order_item_id": str(order_item_id), "barcode": "SAMPLE-001"},
        format="json",
        **headers,
    )
    r2 = api_client.post(
        "/api/v1/lab/samples/receive/",
        {"order_item_id": str(order_item_id), "barcode": "SAMPLE-001"},
        format="json",
        **headers,
    )

    assert r1.status_code in (200, 201), r1.data
    assert r2.status_code in (200, 201), r2.data
    assert r1.data.get("id") == r2.data.get("id")
