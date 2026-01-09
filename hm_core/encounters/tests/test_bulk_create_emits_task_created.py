import pytest

from hm_core.encounters.models import EncounterEvent
from hm_core.tasks.models import Task

pytestmark = pytest.mark.django_db


def test_bulk_created_default_tasks_also_emit_task_created(encounter):
    # Encounter fixture creates default tasks via EncounterService.bulk_create()
    tasks = Task.objects.filter(encounter_id=encounter.id)
    assert tasks.exists()

    for t in tasks:
        assert EncounterEvent.objects.filter(
            encounter_id=encounter.id,
            event_key=f"TASK_CREATED:{t.id}",
            code="TASK_CREATED",
        ).exists()
