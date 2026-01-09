import pytest
from django.utils.timezone import now, timedelta

from hm_core.tasks.models import Task, TaskStatus
from hm_core.tasks.services import TaskService


pytestmark = pytest.mark.django_db


def test_assign_and_unassign_task(tenant_id, facility_id, encounter, user, user2):
    task = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="record-vitals",
        title="Record vitals",
        due_at=now() + timedelta(hours=2),
    )
    assert task.assigned_to_id is None

    # Story: assign
    task = TaskService.assign_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        task_id=task.id,
        assigned_to_id=user.id,
    )
    task.refresh_from_db()
    assert task.assigned_to_id == user.id

    # re-assign to someone else
    task = TaskService.assign_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        task_id=task.id,
        assigned_to_id=user2.id,
    )
    task.refresh_from_db()
    assert task.assigned_to_id == user2.id

    # Story: unassign
    task = TaskService.unassign_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        task_id=task.id,
    )
    task.refresh_from_db()
    assert task.assigned_to_id is None


def test_cannot_assign_done_task(tenant_id, facility_id, encounter, user):
    task = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="doctor-consult",
        title="Doctor consult",
    )

    TaskService.start_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)
    TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)

    with pytest.raises(Exception):
        TaskService.assign_task(
            tenant_id=tenant_id,
            facility_id=facility_id,
            task_id=task.id,
            assigned_to_id=user.id,
        )
