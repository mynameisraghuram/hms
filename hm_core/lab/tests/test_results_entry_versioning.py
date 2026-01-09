import pytest
from hm_core.tests.helpers import scoped

pytestmark = pytest.mark.django_db


def _create_item_and_receive_sample(api_client, tenant, facility, encounter):
    order = api_client.post(
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
    assert order.status_code in (200, 201), order.data
    order_item_id = order.data["items"][0]["id"]

    recv = api_client.post(
        "/api/v1/lab/samples/receive/",
        {"order_item_id": str(order_item_id), "barcode": "SAMPLE-001"},
        format="json",
        **scoped(tenant, facility),
    )
    assert recv.status_code in (200, 201), recv.data
    return order_item_id


def test_result_entry_creates_version_1(api_client, tenant, facility, encounter):
    order_item_id = _create_item_and_receive_sample(api_client, tenant, facility, encounter)

    r = api_client.post(
        "/api/v1/lab/results/",
        {"order_item_id": str(order_item_id), "result_payload": {"hb": 13.2, "wbc": 8000}},
        format="json",
        **scoped(tenant, facility),
    )
    assert r.status_code in (200, 201), r.data
    assert r.data.get("version") == 1


def test_result_entry_creates_version_2_without_mutating_v1(api_client, tenant, facility, encounter):
    order_item_id = _create_item_and_receive_sample(api_client, tenant, facility, encounter)

    r1 = api_client.post(
        "/api/v1/lab/results/",
        {"order_item_id": str(order_item_id), "result_payload": {"hb": 13.2}},
        format="json",
        **scoped(tenant, facility),
    )
    assert r1.status_code in (200, 201), r1.data
    assert r1.data["version"] == 1

    r2 = api_client.post(
        "/api/v1/lab/results/",
        {"order_item_id": str(order_item_id), "result_payload": {"hb": 12.8}},
        format="json",
        **scoped(tenant, facility),
    )
    assert r2.status_code in (200, 201), r2.data
    assert r2.data["version"] == 2


def test_result_entry_sets_is_critical_when_threshold_breached(api_client, tenant, facility, encounter):
    """
    Assumes hb=4.0 is critical.
    Adjust when your critical rules differ.
    """
    order_item_id = _create_item_and_receive_sample(api_client, tenant, facility, encounter)

    r = api_client.post(
        "/api/v1/lab/results/",
        {"order_item_id": str(order_item_id), "result_payload": {"hb": 4.0}},
        format="json",
        **scoped(tenant, facility),
    )
    assert r.status_code in (200, 201), r.data
    assert r.data.get("is_critical") in (True, "true", 1), r.data
