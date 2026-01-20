# backend/hm_core/lab/tests/test_verify_release_gates.py
import pytest
from hm_core.tests.helpers import scoped

pytestmark = pytest.mark.django_db


def _setup_result(api_client, tenant, facility, encounter, critical=False):
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

    payload = {"hb": 4.0} if critical else {"hb": 13.5}
    res = api_client.post(
        "/api/v1/lab/results/",
        {"order_item_id": str(order_item_id), "result_payload": payload},
        format="json",
        **scoped(tenant, facility),
    )
    assert res.status_code in (200, 201), res.data
    return order_item_id, res.data["id"]


def test_verify_then_release_happy_path(api_client, tenant, facility, encounter):
    _, lab_result_id = _setup_result(api_client, tenant, facility, encounter, critical=False)

    v = api_client.post(
        f"/api/v1/lab/results/{lab_result_id}/verify/",
        {},
        format="json",
        **scoped(tenant, facility),
    )
    assert v.status_code in (200, 201), v.data

    rel = api_client.post(
        f"/api/v1/lab/results/{lab_result_id}/release/",
        {},
        format="json",
        **scoped(tenant, facility),
    )
    assert rel.status_code in (200, 201), rel.data
    assert rel.data.get("released_at")


@pytest.mark.parametrize("repeat", [2, 3])
def test_release_retry_storm_no_duplicates(api_client, tenant, facility, encounter, repeat):
    _, lab_result_id = _setup_result(api_client, tenant, facility, encounter, critical=True)

    api_client.post(
        f"/api/v1/lab/results/{lab_result_id}/verify/",
        {},
        format="json",
        **scoped(tenant, facility),
    )

    headers = scoped(tenant, facility)
    headers["HTTP_IDEMPOTENCY_KEY"] = "release-storm-001"

    for _ in range(repeat):
        r = api_client.post(
            f"/api/v1/lab/results/{lab_result_id}/release/",
            {},
            format="json",
            **headers,
        )
        assert r.status_code in (200, 201), r.data

    # Billing event should be created exactly once
    ev = api_client.get(
        f"/api/v1/billing/events/?encounter={encounter.id}",
        **scoped(tenant, facility),
    )
    assert ev.status_code == 200, ev.data

    # billing/events is paginated (Bundle-1)
    if isinstance(ev.data, dict) and "results" in ev.data:
        assert ev.data["count"] == 1, ev.data
        assert len(ev.data["results"]) == 1, ev.data
        ev_rows = ev.data["results"]
    else:
        # fallback for any legacy behavior
        ev_rows = ev.data

    assert len(ev_rows) == 1, ev_rows

    # No Alerts app in Phase-1 core: we do NOT check /alerts/
    # Instead ensure exactly one ACK task exists.
    tasks = api_client.get(
        f"/api/v1/tasks/?encounter={encounter.id}",
        **scoped(tenant, facility),
    )
    assert tasks.status_code == 200, tasks.data

    # tasks may be list OR paginated depending on implementation
    if isinstance(tasks.data, dict) and "results" in tasks.data:
        rows = tasks.data["results"]
    else:
        rows = tasks.data

    ack_tasks = [t for t in rows if t.get("code") in ("critical-result-ack", "CRITICAL_RESULT_ACK")]
    assert len(ack_tasks) == 1, ack_tasks
