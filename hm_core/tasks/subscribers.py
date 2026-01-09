#backend\hm_core\tasks\subscribers.py
from uuid import UUID

from hm_core.common.events import subscribe
from hm_core.tasks.services import TaskService


@subscribe("encounter.created")
def on_encounter_created(payload: dict) -> None:
    tenant_id = UUID(payload["tenant_id"])
    facility_id = UUID(payload["facility_id"])
    encounter_id = UUID(payload["encounter_id"])

    # Phase 0 default OPD tasks (simple starter set)
    TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter_id,
        code="record-vitals",
        title="Record Vitals",
    )
    TaskService.create_task(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter_id,
        code="doctor-consult",
        title="Doctor Consultation",
    )
