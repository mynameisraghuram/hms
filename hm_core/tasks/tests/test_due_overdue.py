import pytest
from django.utils.timezone import now, timedelta

from hm_core.tasks.services import TaskService
from hm_core.tasks.models import TaskStatus

pytestmark = pytest.mark.django_db


def test_due_date_persisted_and_overdue_flags(tenant_id, facility_id, encounter):
    past = now() - timedelta(hours=1)
    future = now() + timedelta(hours=2)

    t1 = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="past",
        title="Past due task",
        due_at=past,
    )
    assert t1.due_at == past
    assert t1.status == TaskStatus.OPEN
    assert t1.is_overdue is True

    t2 = TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter.id,
        code="future",
        title="Future task",
        due_at=future,
    )
    assert t2.is_overdue is False

    # If done, not overdue
    TaskService.start_task(tenant_id=tenant_id, facility_id=facility_id, task_id=t1.id)
    TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=t1.id)
    t1.refresh_from_db()
    assert t1.status == TaskStatus.DONE
    assert t1.is_overdue is False
