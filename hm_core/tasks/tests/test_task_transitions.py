import pytest
from django.utils.timezone import now

from hm_core.tasks.models import TaskStatus
from hm_core.tasks.services import TaskService


pytestmark = pytest.mark.django_db


def test_happy_path_open_to_in_progress_to_done(tenant_id, facility_id, encounter):
    task = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="record-vitals",
        title="Record vitals",
    )
    assert task.status == TaskStatus.OPEN
    assert task.completed_at is None

    task = TaskService.start_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)
    task.refresh_from_db()
    assert task.status == TaskStatus.IN_PROGRESS

    task = TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)
    task.refresh_from_db()
    assert task.status == TaskStatus.DONE
    assert task.completed_at is not None


def test_invalid_transition_open_to_done_is_blocked_by_default(tenant_id, facility_id, encounter):
    task = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="opd-assessment",
        title="OPD Assessment",
    )

    # If you WANT to allow OPEN->DONE, delete this test and codify that rule explicitly.
    with pytest.raises(Exception):
        TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)


def test_cancel_rules(tenant_id, facility_id, encounter):
    task = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="lab-sample",
        title="Collect sample",
    )

    task = TaskService.cancel_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)
    task.refresh_from_db()
    assert task.status == TaskStatus.CANCELLED
    assert task.completed_at is None

    # Cannot start cancelled
    with pytest.raises(Exception):
        TaskService.start_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)

    # Cannot reopen cancelled (rule)
    with pytest.raises(Exception):
        TaskService.reopen_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)


def test_reopen_rules_done_to_in_progress(tenant_id, facility_id, encounter):
    task = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="doctor-consult",
        title="Doctor consult",
    )

    TaskService.start_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)
    TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)

    task.refresh_from_db()
    done_completed_at = task.completed_at
    assert task.status == TaskStatus.DONE
    assert done_completed_at is not None

    task = TaskService.reopen_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)
    task.refresh_from_db()
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.completed_at is None

    # And can be completed again
    TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)
    task.refresh_from_db()
    assert task.status == TaskStatus.DONE
    assert task.completed_at is not None
