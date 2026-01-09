# backend/hm_core/encounters/tests/test_vitals_endpoint.py

import pytest
from hm_core.tasks.models import Task, TaskStatus

pytestmark = pytest.mark.django_db


def test_post_vitals_creates_doc_and_completes_task(api_client, tenant, facility, encounter):
    # Task exists from encounter fixture creation (default tasks)
    t = Task.objects.get(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        code="record-vitals",
    )

    # ensure it's OPEN before vitals
    t.status = TaskStatus.OPEN
    t.completed_at = None
    t.save(update_fields=["status", "completed_at", "updated_at"])

    resp = api_client.post(
        f"/api/v1/encounters/{encounter.id}/vitals/",
        data={"temperature_c": 38.2, "pulse_bpm": 98},
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
        HTTP_X_FACILITY_ID=str(facility.id),
    )

    assert resp.status_code == 201
    assert resp.data["document"]["kind"] == "VITALS"

    t.refresh_from_db()
    assert t.status == TaskStatus.DONE
    assert t.completed_at is not None
