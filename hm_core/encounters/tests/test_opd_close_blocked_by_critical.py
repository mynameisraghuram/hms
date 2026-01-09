# backend/hm_core/encounters/tests/test_opd_close_blocked_by_critical.py

import pytest

from django.utils import timezone

from hm_core.tasks.models import Task, TaskStatus


pytestmark = pytest.mark.django_db


def _scope(tenant, facility):
    return {"HTTP_X_TENANT_ID": str(tenant.id), "HTTP_X_FACILITY_ID": str(facility.id)}


def test_opd_close_blocked_when_unacked_critical_alert_exists(api_client, tenant, facility, encounter):
    # Create the ACK task (this replaces Alerts app dependency)
    Task.objects.get_or_create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        code="critical-result-ack",
        defaults={"title": "Acknowledge Critical Result", "status": TaskStatus.OPEN},
    )

    res = api_client.post(
        f"/api/v1/encounters/{encounter.id}/close/",
        {},
        format="json",
        **_scope(tenant, facility),
    )

    # We return 409 with close-gate payload when blocked
    assert res.status_code == 409, res.data
    assert res.data.get("can_close") is False
    # Ensure the block reason is critical ack
    missing = res.data.get("missing") or []
    assert any(m.get("type") == "CRITICAL_ACK" for m in missing), missing


def test_opd_close_allowed_after_ack(api_client, tenant, facility, encounter):
    # Create ACK task then mark it DONE
    t, _ = Task.objects.get_or_create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        code="critical-result-ack",
        defaults={"title": "Acknowledge Critical Result", "status": TaskStatus.OPEN},
    )
    t.status = TaskStatus.DONE
    t.completed_at = t.completed_at or timezone.now()
    t.save(update_fields=["status", "completed_at", "updated_at"])

    res = api_client.post(
        f"/api/v1/encounters/{encounter.id}/close/",
        {},
        format="json",
        **_scope(tenant, facility),
    )
    assert res.status_code in (200, 201), res.data
    assert res.data.get("status") == "CLOSED"
