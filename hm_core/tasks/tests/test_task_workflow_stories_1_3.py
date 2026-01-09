import pytest
from django.core.exceptions import ValidationError

from hm_core.tasks.models import TaskStatus
from hm_core.tasks.services import TaskService

pytestmark = pytest.mark.django_db


def test_assign_unassign_story_1(tenant_id, facility_id, encounter, user, user2):
    task = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="record-vitals",
        title="Record Vitals",
    )
    assert task.assigned_to_id is None
    assert task.status == TaskStatus.OPEN

    # assign
    task = TaskService.assign_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        task_id=task.id,
        assigned_to_id=user.id,
    )
    task.refresh_from_db()
    assert task.assigned_to_id == user.id

    # reassign
    task = TaskService.assign_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        task_id=task.id,
        assigned_to_id=user2.id,
    )
    task.refresh_from_db()
    assert task.assigned_to_id == user2.id

    # unassign
    task = TaskService.unassign_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        task_id=task.id,
    )
    task.refresh_from_db()
    assert task.assigned_to_id is None


def test_status_happy_path_open_to_in_progress_to_done_story_2(tenant_id, facility_id, encounter):
    task = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="doctor-consult",
        title="Doctor Consult",
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


def test_enforce_no_open_to_done_by_default(tenant_id, facility_id, encounter):
    task = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="t1",
        title="T1",
    )
    # Rule: enforce OPEN → IN_PROGRESS → DONE
    with pytest.raises(ValidationError):
        TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)


def test_cancel_rules_story_2(tenant_id, facility_id, encounter):
    task = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="lab-sample",
        title="Collect sample",
    )
    assert task.status == TaskStatus.OPEN

    task = TaskService.cancel_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)
    task.refresh_from_db()
    assert task.status == TaskStatus.CANCELLED
    assert task.completed_at is None

    with pytest.raises(ValidationError):
        TaskService.start_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)

    with pytest.raises(ValidationError):
        TaskService.reopen_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)


def test_reopen_rules_done_to_in_progress_story_2(tenant_id, facility_id, encounter):
    task = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="critical-result-ack",
        title="Ack critical result",
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

    # can complete again
    TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)
    task.refresh_from_db()
    assert task.status == TaskStatus.DONE
    assert task.completed_at is not None
