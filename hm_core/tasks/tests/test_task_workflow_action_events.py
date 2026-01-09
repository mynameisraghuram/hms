import pytest
from django.utils.timezone import now

from hm_core.encounters.models import EncounterEvent
from hm_core.tasks.models import TaskStatus
from hm_core.tasks.services import TaskService

pytestmark = pytest.mark.django_db


def events_for(encounter, code: str):
    return EncounterEvent.objects.filter(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code=code,
    )


def test_task_assigned_event_emitted_once_per_same_assignee(encounter, django_user_model):
    assignee = django_user_model.objects.create_user(username="assignee_evt", password="x")

    task = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-assign",
        title="Assign me",
    )

    TaskService.assign_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        task_id=task.id,
        assigned_to_id=assignee.id,
    )
    TaskService.assign_task(  # second call same assignee -> no-op, no duplicate event
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        task_id=task.id,
        assigned_to_id=assignee.id,
    )

    qs = events_for(encounter, "TASK_ASSIGNED")
    assert qs.count() == 1
    ev = qs.first()
    assert ev.event_key == f"TASK_ASSIGNED:{task.id}:{assignee.id}"
    assert ev.meta["assigned_to_id"] == assignee.id


def test_task_unassigned_event_emitted_once(encounter, django_user_model):
    assignee = django_user_model.objects.create_user(username="assignee_evt2", password="x")

    task = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-unassign",
        title="Unassign me",
        assigned_to_id=assignee.id,
    )

    TaskService.unassign_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        task_id=task.id,
    )
    TaskService.unassign_task(  # already unassigned -> no-op, no duplicate
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        task_id=task.id,
    )

    qs = events_for(encounter, "TASK_UNASSIGNED")
    assert qs.count() == 1
    ev = qs.first()
    assert ev.event_key == f"TASK_UNASSIGNED:{task.id}:{assignee.id}"
    assert ev.meta["previous_assigned_to_id"] == assignee.id


def test_task_started_event_emitted(encounter):
    task = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-start",
        title="Start me",
    )

    TaskService.start_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        task_id=task.id,
    )

    qs = events_for(encounter, "TASK_STARTED")
    assert qs.count() == 1
    ev = qs.first()
    assert ev.event_key == f"TASK_STARTED:{task.id}"
    assert ev.meta["status"] == TaskStatus.IN_PROGRESS


def test_task_cancelled_event_emitted_once(encounter):
    task = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-cancel",
        title="Cancel me",
    )

    TaskService.cancel_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        task_id=task.id,
    )
    TaskService.cancel_task(  # already cancelled -> no-op, no duplicate
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        task_id=task.id,
    )

    qs = events_for(encounter, "TASK_CANCELLED")
    assert qs.count() == 1
    ev = qs.first()
    assert ev.event_key == f"TASK_CANCELLED:{task.id}"
    assert ev.meta["status"] == TaskStatus.CANCELLED


def test_task_reopened_event_emitted(encounter):
    task = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-reopen",
        title="Reopen me",
    )

    TaskService.start_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        task_id=task.id,
    )

    TaskService.complete_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        task_id=task.id,
        completed_at=now(),
    )

    task.refresh_from_db()
    prev_completed_at = task.completed_at.isoformat()

    TaskService.reopen_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        task_id=task.id,
    )

    qs = events_for(encounter, "TASK_REOPENED")
    assert qs.count() == 1
    ev = qs.first()
    assert ev.event_key == f"TASK_REOPENED:{task.id}:{prev_completed_at}"
    assert ev.meta["previous_completed_at"] == prev_completed_at
    assert ev.meta["status"] == TaskStatus.IN_PROGRESS
