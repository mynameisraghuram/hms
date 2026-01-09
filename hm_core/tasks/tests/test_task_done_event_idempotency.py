import pytest
from hm_core.encounters.models import EncounterEvent
from hm_core.tasks.services import TaskService
from hm_core.tasks.models import TaskStatus

pytestmark = pytest.mark.django_db


def test_task_done_event_is_idempotent_by_event_key(tenant_id, facility_id, encounter):
    task = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="doctor-consult",
        title="Doctor Consult",
    )

    TaskService.start_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)

    # complete twice
    TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)
    TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)

    task.refresh_from_db()
    assert task.status == TaskStatus.DONE

    assert EncounterEvent.objects.filter(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        event_key=f"TASK_DONE:{task.id}",
        code="TASK_DONE",
    ).count() == 1
