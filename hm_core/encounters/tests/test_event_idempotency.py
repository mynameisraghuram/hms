import pytest
from django.utils.timezone import now

from hm_core.encounters.models import EncounterEvent
from hm_core.tasks.models import Task
from hm_core.clinical_docs.models import EncounterDocument

pytestmark = pytest.mark.django_db


def _count(encounter_id, code: str) -> int:
    return EncounterEvent.objects.filter(encounter_id=encounter_id, code=code).count()


def test_encounter_created_event_is_idempotent(encounter):
    """
    Encounter created signal should be idempotent.
    Saving the same encounter again must NOT create another ENCOUNTER_CREATED event.
    """
    encounter_id = encounter.id

    # after fixture creation, we expect at least 1 created event
    c1 = _count(encounter_id, "ENCOUNTER_CREATED")
    assert c1 == 1, f"Expected exactly 1 ENCOUNTER_CREATED, got {c1}"

    # double-save (no transition)
    encounter.save()
    c2 = _count(encounter_id, "ENCOUNTER_CREATED")
    assert c2 == 1, f"ENCOUNTER_CREATED duplicated after save(): {c2}"


def test_task_done_event_is_idempotent(tenant, facility, encounter):
    """
    Completing the same task twice must not duplicate TASK_DONE event.
    """
    # task exists from encounter fixture creation
    t = Task.objects.get(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        code="record-vitals",
    )

    # First completion
    t.status = "DONE"
    t.completed_at = t.completed_at or now()
    t.save(update_fields=["status", "completed_at", "updated_at"])

    c1 = _count(encounter.id, "TASK_DONE")
    assert c1 == 1, f"Expected exactly 1 TASK_DONE after first completion, got {c1}"

    # Second completion (same values) - should not create new event
    t.status = "DONE"
    t.completed_at = t.completed_at  # unchanged
    t.save(update_fields=["status", "completed_at", "updated_at"])

    c2 = _count(encounter.id, "TASK_DONE")
    assert c2 == 1, f"TASK_DONE duplicated after second save(): {c2}"


def test_task_created_event_is_not_duplicated_by_second_save(tenant, facility, encounter):
    """
    TASK_CREATED should exist once per task.
    Saving the task again should not create another TASK_CREATED.
    """
    t = Task.objects.get(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        code="record-vitals",
    )

    # This depends on whether your EncounterService emits TASK_CREATED for bulk_create
    # OR your backfill already created it. Either way, after creation it must be 1.
    c1 = EncounterEvent.objects.filter(encounter_id=encounter.id, event_key=f"TASK_CREATED:{t.id}").count()
    assert c1 == 1, f"Expected exactly 1 TASK_CREATED for task {t.id}, got {c1}"

    # Saving task again should not create another TASK_CREATED
    t.title = t.title  # no-op
    t.save()

    c2 = EncounterEvent.objects.filter(encounter_id=encounter.id, event_key=f"TASK_CREATED:{t.id}").count()
    assert c2 == 1, f"TASK_CREATED duplicated after task.save(): {c2}"


def test_doc_authored_is_idempotent_on_double_save(tenant, facility, encounter):
    """
    DOC_AUTHORED uses event_key=DOC_AUTHORED:<doc_id>.
    Creating the doc creates the event.
    Saving the doc again should not create a second event.
    """
    d = EncounterDocument.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        kind="VITALS",
        content={"temperature_c": 38.2, "pulse_bpm": 98},
    )

    c1 = EncounterEvent.objects.filter(encounter_id=encounter.id, event_key=f"DOC_AUTHORED:{d.id}").count()
    assert c1 == 1, f"Expected exactly 1 DOC_AUTHORED for doc {d.id}, got {c1}"

    # Double-save the doc (no-op)
    d.content = d.content
    d.save()

    c2 = EncounterEvent.objects.filter(encounter_id=encounter.id, event_key=f"DOC_AUTHORED:{d.id}").count()
    assert c2 == 1, f"DOC_AUTHORED duplicated after doc.save(): {c2}"
