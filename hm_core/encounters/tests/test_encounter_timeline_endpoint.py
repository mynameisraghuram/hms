#hm_core/encounters/tests/test_encounter_timeline_endpoint.py
import pytest

from hm_core.conftest import scope_headers
from hm_core.encounters.models import EncounterEvent
from hm_core.tasks.models import Task
from hm_core.clinical_docs.models import EncounterDocument


pytestmark = pytest.mark.django_db


def test_timeline_empty_is_ok(api_client, tenant, facility, encounter):
    # NOTE: your encounter fixture likely emits ENCOUNTER_CREATED automatically via signals.
    resp = api_client.get(
        f"/api/v1/encounters/{encounter.id}/timeline/",
        **scope_headers(tenant, facility),
    )
    assert resp.status_code == 200
    assert "items" in resp.data
    assert isinstance(resp.data["items"], list)


def test_timeline_includes_tasks_and_docs(api_client, tenant, facility, encounter):
    # Task already exists from encounter fixture (record-vitals).
    # Create a doc -> should emit DOC_AUTHORED event.
    EncounterDocument.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        kind="VITALS",
        content={"temperature_c": 38.2, "pulse_bpm": 98},
    )

    # Mark task done -> should emit TASK_DONE event (if your service sets completed_at).
    t = Task.objects.get(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        code="record-vitals",
    )
    # simulate completion without service (still triggers signals)
    t.completed_at = t.completed_at or t.updated_at
    t.status = "DONE"
    t.save(update_fields=["status", "completed_at", "updated_at"])

    resp = api_client.get(
        f"/api/v1/encounters/{encounter.id}/timeline/",
        **scope_headers(tenant, facility),
    )
    assert resp.status_code == 200
    items = resp.data["items"]

    codes = [i["code"] for i in items]

    # Lifecycle event
    assert "ENCOUNTER_CREATED" in codes

    # Task events
    assert "TASK_CREATED" in codes
    assert "TASK_DONE" in codes

    # Doc event
    assert "DOC_AUTHORED" in codes

    # Bonus: validate events really exist in DB (not computed)
    assert EncounterEvent.objects.filter(encounter_id=encounter.id, code="TASK_CREATED").exists()
    assert EncounterEvent.objects.filter(encounter_id=encounter.id, code="DOC_AUTHORED").exists()
