# backend/hm_core/encounters/services.py
from __future__ import annotations

from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.timezone import now

from hm_core.audit.services import AuditService
from hm_core.clinical_docs.models import EncounterDocument
from hm_core.common.events import publish
from hm_core.encounters.constants import EncounterStatus
from hm_core.encounters.models import Encounter
from hm_core.encounters.signals._emit import emit_event
from hm_core.patients.models import Patient
from hm_core.rules.engine import RuleEngine
from hm_core.tasks.models import Task, TaskStatus
from hm_core.tasks.services import TaskService


class EncounterService:
    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def _emit_task_created_events(*, tenant_id, facility_id, encounter_id, tasks) -> int:
        """
        Emit TASK_CREATED events for tasks created via bulk operations.

        Why:
        - bulk_create bypasses model save() signals
        - emit_event is idempotent via unique event_key
        """
        count = 0
        for task in tasks:
            ts = getattr(task, "created_at", None) or now()
            emit_event(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=encounter_id,
                event_key=f"TASK_CREATED:{task.id}",
                code="TASK_CREATED",
                title="Task created",
                timestamp=ts,
                meta={
                    "task_id": str(task.id),
                    "task_code": task.code,
                    "task_title": task.title,
                    "status": task.status,
                },
            )
            count += 1
        return count

    # ---------------------------------------------------------------------
    # Encounter lifecycle writes
    # ---------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def create(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        patient_id: UUID,
        actor_user_id: int | None,
        reason: str = "",
        attending_doctor_id: int | None = None,
        scheduled_at=None,
    ) -> Encounter:
        patient = Patient.objects.get(
            id=patient_id,
            tenant_id=tenant_id,
            facility_id=facility_id,
        )

        try:
            enc = Encounter.objects.create(
                tenant_id=tenant_id,
                facility_id=facility_id,
                patient=patient,
                status=EncounterStatus.CREATED,
                reason=reason,
                attending_doctor_id=attending_doctor_id,
                created_by_id=actor_user_id,
                scheduled_at=scheduled_at,
            )
        except IntegrityError:
            raise ValueError("Active encounter already exists for this patient in this facility.")

        # ENCOUNTER_CREATED (idempotent)
        emit_event(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=enc.id,
            event_key=f"ENCOUNTER_CREATED:{enc.id}",
            code="ENCOUNTER_CREATED",
            title="Encounter created",
            timestamp=getattr(enc, "created_at", None) or now(),
            meta={
                "encounter_id": str(enc.id),
                "patient_id": str(patient_id),
                "status": enc.status,
            },
        )

        # Default Phase-0 tasks (bulk_create bypasses signals)
        default_tasks = [
            {"code": "record-vitals", "title": "Record Vitals"},
            {"code": "doctor-consult", "title": "Doctor Consultation"},
        ]

        task_objs = [
            Task(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=enc.id,
                code=t["code"],
                title=t["title"],
                status=TaskStatus.OPEN,
            )
            for t in default_tasks
        ]

        created_tasks = Task.objects.bulk_create(task_objs)

        EncounterService._emit_task_created_events(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=enc.id,
            tasks=created_tasks,
        )

        AuditService.log(
            event_code="encounter.created",
            entity_type="Encounter",
            entity_id=enc.id,
            tenant_id=tenant_id,
            facility_id=facility_id,
            actor_user_id=actor_user_id,
            metadata={"patient_id": str(patient_id)},
        )

        publish(
            "encounter.created",
            {
                "tenant_id": str(tenant_id),
                "facility_id": str(facility_id),
                "encounter_id": str(enc.id),
                "actor_user_id": actor_user_id,
            },
        )

        return enc

    @staticmethod
    @transaction.atomic
    def checkin(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        encounter_id: UUID,
        actor_user_id: int | None,
    ) -> Encounter:
        enc = Encounter.objects.get(id=encounter_id, tenant_id=tenant_id, facility_id=facility_id)
        enc.status = EncounterStatus.CHECKED_IN
        enc.checked_in_at = timezone.now()
        enc.save(update_fields=["status", "checked_in_at", "updated_at"])

        emit_event(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=enc.id,
            event_key=f"ENCOUNTER_CHECKED_IN:{enc.id}",
            code="ENCOUNTER_CHECKED_IN",
            title="Encounter checked in",
            timestamp=timezone.now(),
            meta={"encounter_id": str(enc.id)},
        )

        AuditService.log(
            event_code="encounter.checked_in",
            entity_type="Encounter",
            entity_id=enc.id,
            tenant_id=tenant_id,
            facility_id=facility_id,
            actor_user_id=actor_user_id,
            metadata={},
        )
        return enc

    @staticmethod
    @transaction.atomic
    def start_consult(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        encounter_id: UUID,
        actor_user_id: int | None,
    ) -> Encounter:
        enc = Encounter.objects.get(id=encounter_id, tenant_id=tenant_id, facility_id=facility_id)
        enc.status = EncounterStatus.IN_CONSULT
        enc.consult_started_at = timezone.now()
        enc.save(update_fields=["status", "consult_started_at", "updated_at"])

        TaskService.create_task(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=enc.id,
            code="doctor-consult",
            title="Doctor Consultation",
            assigned_to_id=enc.attending_doctor_id,
        )

        emit_event(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=enc.id,
            event_key=f"CONSULT_STARTED:{enc.id}",
            code="CONSULT_STARTED",
            title="Consult started",
            timestamp=timezone.now(),
            meta={"encounter_id": str(enc.id)},
        )

        AuditService.log(
            event_code="consult.started",
            entity_type="Encounter",
            entity_id=enc.id,
            tenant_id=tenant_id,
            facility_id=facility_id,
            actor_user_id=actor_user_id,
            metadata={},
        )
        return enc

    # ---------------------------------------------------------------------
    # Clinical doc writes (moved out of views)
    # ---------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def record_vitals(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        encounter_id: UUID,
        authored_by_id: int | None,
        vitals: dict,
    ) -> EncounterDocument:
        """
        Persist VITALS and auto-complete 'record-vitals' task.
        Uses update_or_create so repeated calls are idempotent for the same encounter+kind.
        """
        doc, _ = EncounterDocument.objects.update_or_create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            kind="VITALS",
            defaults={
                "content": dict(vitals),
                "authored_by_id": authored_by_id,
            },
        )

        Task.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            code="record-vitals",
        ).update(
            status=TaskStatus.DONE,
            completed_at=timezone.now(),
            updated_at=timezone.now(),
        )

        return doc

    @staticmethod
    @transaction.atomic
    def save_assessment(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        encounter_id: UUID,
        authored_by_id: int | None,
        content: dict,
    ) -> EncounterDocument:
        """
        Persist ASSESSMENT and auto-complete 'doctor-consult' task
        (tests expect DONE + completed_at).
        """
        doc, _ = EncounterDocument.objects.update_or_create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            kind="ASSESSMENT",
            defaults={
                "content": dict(content),
                "authored_by_id": authored_by_id,
            },
        )

        Task.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            code="doctor-consult",
        ).update(
            status=TaskStatus.DONE,
            completed_at=timezone.now(),
            updated_at=timezone.now(),
        )

        return doc

    @staticmethod
    @transaction.atomic
    def save_plan(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        encounter_id: UUID,
        authored_by_id: int | None,
        content: dict,
    ) -> EncounterDocument:
        doc, _ = EncounterDocument.objects.update_or_create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            kind="PLAN",
            defaults={
                "content": dict(content),
                "authored_by_id": authored_by_id,
            },
        )
        return doc

    # ---------------------------------------------------------------------
    # Close gate (read-ish payload; kept here for API stability)
    # ---------------------------------------------------------------------
    @staticmethod
    def get_close_gate(*, tenant_id: UUID, facility_id: UUID, encounter_id: UUID) -> dict:
        """
        Advisory close-gate payload (used by GET /close-gate/).

        We intentionally return BOTH:
          - structured lists: missing_docs, missing_tasks
          - a flat "missing" list that includes labels + codes
            (needed because some tests assert presence of "tasks_open"/"TASKS")
        """
        result = RuleEngine.check_encounter_close_gate(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
        )

        missing_map = getattr(result, "missing", {}) or {}
        docs_missing = list(missing_map.get("docs_missing") or [])
        tasks_open = list(missing_map.get("tasks_open") or [])

        missing_list: list[str] = []
        if docs_missing:
            missing_list += ["DOCS", "docs_missing", *docs_missing]
        if tasks_open:
            missing_list += ["TASKS", "tasks_open", *tasks_open]

        # Safety advisory (helpful for UI)
        try:
            RuleEngine.enforce_critical_ack_gate(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=encounter_id,
            )
        except Exception:
            missing_list += ["SAFETY", "CRITICAL_ACK", "critical-result-ack"]

        return {
            "ok": bool(getattr(result, "ok", False)),
            "can_close": bool(getattr(result, "can_close", False)),
            "missing_docs": docs_missing,
            "missing_tasks": tasks_open,
            "missing": missing_list,
            "reasons": [
                {"type": "DOCS", "missing": docs_missing},
                {"type": "TASKS", "open": tasks_open},
            ],
        }

    # ---------------------------------------------------------------------
    # Close actions
    # ---------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def close(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        encounter_id: UUID,
        actor_user_id: int | None,
    ) -> Encounter:
        """
        Close encounter (OPD quick close).

        IMPORTANT:
        - /close/ enforces ONLY hard blockers (critical ack)
        - /close-gate/ is the completeness checker
        """
        RuleEngine.enforce_critical_ack_gate(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
        )

        enc = Encounter.objects.get(id=encounter_id, tenant_id=tenant_id, facility_id=facility_id)
        enc.status = EncounterStatus.CLOSED
        enc.closed_at = timezone.now()
        enc.save(update_fields=["status", "closed_at", "updated_at"])

        TaskService.close_all_for_encounter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=enc.id,
        )

        emit_event(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=enc.id,
            event_key=f"ENCOUNTER_CLOSED:{enc.id}",
            code="ENCOUNTER_CLOSED",
            title="Encounter closed",
            timestamp=timezone.now(),
            meta={"actor_user_id": actor_user_id},
        )

        return enc

    @staticmethod
    @transaction.atomic
    def close_strict(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        encounter_id: UUID,
        actor_user_id: int | None,
    ) -> Encounter:
        """
        Close encounter with FULL completeness enforcement.
        Used by /close-strict/.
        """
        RuleEngine.enforce_encounter_close_gate(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
        )
        return EncounterService.close(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            actor_user_id=actor_user_id,
        )
