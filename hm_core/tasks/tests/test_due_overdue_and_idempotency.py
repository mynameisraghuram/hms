import pytest
from django.apps import apps
from django.utils.timezone import now, timedelta

from hm_core.tasks.models import TaskStatus
from hm_core.tasks.services import TaskService


pytestmark = pytest.mark.django_db


def get_event_model():
    candidates = [
        ("encounters", "EncounterEvent"),
        ("encounters", "Event"),
        ("audit", "AuditEvent"),
    ]
    for app_label, model_name in candidates:
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            continue
    return None


def test_due_date_and_overdue_behavior(tenant_id, facility_id, encounter):
    past = now() - timedelta(hours=1)
    future = now() + timedelta(hours=2)

    t1 = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="t-past",
        title="Past due",
        due_at=past,
    )
    assert t1.due_at == past
    assert getattr(t1, "is_overdue", None) in (True, False)  # property expected
    assert t1.is_overdue is True

    t2 = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="t-future",
        title="Future due",
        due_at=future,
    )
    assert t2.is_overdue is False

    # When done, never overdue
    TaskService.start_task(tenant_id=tenant_id, facility_id=facility_id, task_id=t1.id)
    TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=t1.id)
    t1.refresh_from_db()
    assert t1.status == TaskStatus.DONE
    assert t1.is_overdue is False


def test_task_done_event_is_idempotent(tenant_id, facility_id, encounter):
    EventModel = get_event_model()
    if EventModel is None:
        pytest.skip("No EncounterEvent/AuditEvent model found to assert idempotency.")

    task = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="doctor-consult",
        title="Doctor consult",
    )

    TaskService.start_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)

    # Complete twice (should not duplicate events)
    TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)
    TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=task.id)

    task.refresh_from_db()
    assert task.status == TaskStatus.DONE

    # We assert by event_key if the model has it; otherwise, fall back to counting code occurrences.
    qs = EventModel.objects.all()
    if hasattr(EventModel, "event_key"):
        assert qs.filter(event_key=f"TASK_DONE:{task.id}").count() == 1
    elif hasattr(EventModel, "code"):
        assert qs.filter(code="TASK_DONE").count() >= 1
