# backend/hm_core/tasks/services.py

from __future__ import annotations

from typing import Optional
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.timezone import now

from hm_core.encounters.signals._emit import emit_event
from hm_core.tasks.models import Task, TaskStatus


class TaskService:
    """
    Task write-model operations (workflow + assignment).

    Notes:
    - Strict workflow: OPEN -> IN_PROGRESS -> DONE (complete_task requires IN_PROGRESS).
    - Backfill/repair: mark_done/backfill_mark_done can mark DONE by (encounter_id, code).
    - Events are written immediately (not on_commit) due to pytest transaction semantics.
    """

    DEFAULT_TITLES = {
        "record-vitals": "Record Vitals",
        "doctor-consult": "Doctor Consultation",
        "critical-result-ack": "Acknowledge Critical Result",
    }

    # -------------------------
    # Internal helpers
    # -------------------------
    @staticmethod
    def _get_scoped(*, tenant_id: UUID, facility_id: UUID, task_id: UUID) -> Task:
        return Task.objects.get(id=task_id, tenant_id=tenant_id, facility_id=facility_id)

    @staticmethod
    def _touch_updated_at(task: Task, update_fields: list[str]) -> None:
        if hasattr(task, "updated_at"):
            task.updated_at = now()
            update_fields.append("updated_at")

    # -------------------------
    # Event helper (idempotent via event_key uniqueness)
    # -------------------------
    @staticmethod
    def _emit_task_event(
        *,
        task: Task,
        event_code: str,
        title: str,
        event_key: str,
        meta: Optional[dict] = None,
        timestamp=None,
    ) -> None:
        if timestamp is None:
            timestamp = now()

        payload = {
            "task_id": str(task.id),
            "task_code": task.code,
            "task_title": task.title,
            "status": task.status,
            "assigned_to_id": task.assigned_to_id,
        }
        if meta:
            payload.update(meta)

        emit_event(
            tenant_id=task.tenant_id,
            facility_id=task.facility_id,
            encounter_id=task.encounter_id,
            event_key=event_key,
            code=event_code,
            title=title,
            timestamp=timestamp,
            meta=payload,
        )

    # -------------------------
    # Create (idempotent)
    # -------------------------
    @staticmethod
    @transaction.atomic
    def create_task(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        encounter_id: UUID,
        code: str,
        title: str,
        assigned_to_id: Optional[int] = None,
        due_at=None,
    ) -> Task:
        """
        Idempotent per (tenant_id, facility_id, encounter_id, code).
        Emits TASK_CREATED only when the task is newly created.
        """
        task, created = Task.objects.get_or_create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            code=code,
            defaults={
                "title": title,
                "status": TaskStatus.OPEN,
                "assigned_to_id": assigned_to_id,
                "due_at": due_at,
            },
        )

        # If it already exists, optionally refresh fields WITHOUT re-emitting TASK_CREATED.
        if not created:
            changed_fields: list[str] = []

            if title and task.title != title:
                task.title = title
                changed_fields.append("title")

            # Only update assignment if explicitly provided
            if assigned_to_id is not None and task.assigned_to_id != assigned_to_id:
                task.assigned_to_id = assigned_to_id
                changed_fields.append("assigned_to")

            if due_at is not None and task.due_at != due_at:
                task.due_at = due_at
                changed_fields.append("due_at")

            if changed_fields:
                TaskService._touch_updated_at(task, changed_fields)
                task.save(update_fields=changed_fields)

            return task

        # Newly created => emit TASK_CREATED (idempotent via event_key uniqueness)
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
                "assigned_to_id": task.assigned_to_id,
            },
        )
        return task

    # -------------------------
    # Assignment (Story 1) + Events
    # -------------------------
    @staticmethod
    @transaction.atomic
    def assign_task(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        task_id: UUID,
        assigned_to_id: int,
    ) -> Task:
        task = TaskService._get_scoped(tenant_id=tenant_id, facility_id=facility_id, task_id=task_id)

        if task.status in {TaskStatus.DONE, TaskStatus.CANCELLED}:
            raise ValidationError("Cannot assign DONE/CANCELLED task.")

        # Idempotent no-op: same assignee
        if task.assigned_to_id == assigned_to_id:
            return task

        task.assigned_to_id = assigned_to_id
        update_fields = ["assigned_to"]
        TaskService._touch_updated_at(task, update_fields)
        task.save(update_fields=update_fields)

        TaskService._emit_task_event(
            task=task,
            event_code="TASK_ASSIGNED",
            title="Task assigned",
            event_key=f"TASK_ASSIGNED:{task.id}:{assigned_to_id}",
        )
        return task

    @staticmethod
    @transaction.atomic
    def unassign_task(*, tenant_id: UUID, facility_id: UUID, task_id: UUID) -> Task:
        task = TaskService._get_scoped(tenant_id=tenant_id, facility_id=facility_id, task_id=task_id)

        if task.status in {TaskStatus.DONE, TaskStatus.CANCELLED}:
            raise ValidationError("Cannot unassign DONE/CANCELLED task.")

        # Idempotent no-op: already unassigned
        if task.assigned_to_id is None:
            return task

        prev_assigned_to_id = task.assigned_to_id
        task.assigned_to_id = None
        update_fields = ["assigned_to"]
        TaskService._touch_updated_at(task, update_fields)
        task.save(update_fields=update_fields)

        TaskService._emit_task_event(
            task=task,
            event_code="TASK_UNASSIGNED",
            title="Task unassigned",
            event_key=f"TASK_UNASSIGNED:{task.id}:{prev_assigned_to_id}",
            meta={"previous_assigned_to_id": prev_assigned_to_id},
        )
        return task

    # -------------------------
    # Workflow (Story 2) + Events
    # OPEN -> IN_PROGRESS -> DONE
    # Cancel rules, Reopen rules
    # -------------------------
    @staticmethod
    @transaction.atomic
    def start_task(*, tenant_id: UUID, facility_id: UUID, task_id: UUID) -> Task:
        task = TaskService._get_scoped(tenant_id=tenant_id, facility_id=facility_id, task_id=task_id)

        if task.status != TaskStatus.OPEN:
            raise ValidationError("Only OPEN task can be started.")

        task.status = TaskStatus.IN_PROGRESS
        update_fields = ["status"]
        TaskService._touch_updated_at(task, update_fields)
        task.save(update_fields=update_fields)

        TaskService._emit_task_event(
            task=task,
            event_code="TASK_STARTED",
            title="Task started",
            event_key=f"TASK_STARTED:{task.id}",
        )
        return task

    @staticmethod
    @transaction.atomic
    def complete_task(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        task_id: UUID,
        completed_at=None,
    ) -> Task:
        """
        Strict completion: only IN_PROGRESS -> DONE.
        Emits TASK_DONE idempotently.
        """
        task = TaskService._get_scoped(tenant_id=tenant_id, facility_id=facility_id, task_id=task_id)

        # Idempotent: if already DONE, do not mutate completed_at
        if task.status == TaskStatus.DONE and task.completed_at:
            return task

        if task.status != TaskStatus.IN_PROGRESS:
            raise ValidationError("Only IN_PROGRESS task can be completed.")

        task.status = TaskStatus.DONE
        task.completed_at = completed_at or now()

        update_fields = ["status", "completed_at"]
        TaskService._touch_updated_at(task, update_fields)
        task.save(update_fields=update_fields)

        emit_event(
            tenant_id=task.tenant_id,
            facility_id=task.facility_id,
            encounter_id=task.encounter_id,
            event_key=f"TASK_DONE:{task.id}",
            code="TASK_DONE",
            title="Task completed",
            timestamp=task.completed_at,
            meta={
                "task_id": str(task.id),
                "task_code": task.code,
                "task_title": task.title,
                "status": task.status,
                "assigned_to_id": task.assigned_to_id,
            },
        )
        return task

    @staticmethod
    @transaction.atomic
    def reopen_task(*, tenant_id: UUID, facility_id: UUID, task_id: UUID) -> Task:
        """
        DONE -> IN_PROGRESS, clears completed_at.
        Emits TASK_REOPENED.
        """
        task = TaskService._get_scoped(tenant_id=tenant_id, facility_id=facility_id, task_id=task_id)

        if task.status != TaskStatus.DONE:
            raise ValidationError("Only DONE task can be reopened.")

        # make event_key stable per completion cycle
        prev_completed_at = task.completed_at.isoformat() if task.completed_at else "none"

        task.status = TaskStatus.IN_PROGRESS
        task.completed_at = None

        update_fields = ["status", "completed_at"]
        TaskService._touch_updated_at(task, update_fields)
        task.save(update_fields=update_fields)

        TaskService._emit_task_event(
            task=task,
            event_code="TASK_REOPENED",
            title="Task reopened",
            event_key=f"TASK_REOPENED:{task.id}:{prev_completed_at}",
            meta={"previous_completed_at": prev_completed_at},
        )
        return task

    @staticmethod
    @transaction.atomic
    def cancel_task(*, tenant_id: UUID, facility_id: UUID, task_id: UUID) -> Task:
        """
        OPEN/IN_PROGRESS -> CANCELLED.
        Cannot cancel DONE.
        Emits TASK_CANCELLED once (idempotent).
        """
        task = TaskService._get_scoped(tenant_id=tenant_id, facility_id=facility_id, task_id=task_id)

        if task.status == TaskStatus.DONE:
            raise ValidationError("Cannot cancel DONE task.")

        if task.status == TaskStatus.CANCELLED:
            return task

        prev_status = task.status
        task.status = TaskStatus.CANCELLED
        task.completed_at = None

        update_fields = ["status", "completed_at"]
        TaskService._touch_updated_at(task, update_fields)
        task.save(update_fields=update_fields)

        TaskService._emit_task_event(
            task=task,
            event_code="TASK_CANCELLED",
            title="Task cancelled",
            event_key=f"TASK_CANCELLED:{task.id}",
            meta={"previous_status": prev_status},
        )
        return task

    # -------------------------
    # Backfill/Repair (Story 3 utilities)
    # -------------------------
    @staticmethod
    @transaction.atomic
    def backfill_mark_done(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        encounter_id: UUID,
        code: str,
    ) -> int:
        """
        Backfill/repair behavior:
        - Ensures a task exists and is DONE by (encounter_id, code).
        - Does NOT enforce workflow.
        - Emits TASK_DONE idempotently.
        Returns 1 if it changed/created a DONE task, else 0.
        """
        ts = now()

        task, created = Task.objects.get_or_create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            code=code,
            defaults={
                "title": TaskService.DEFAULT_TITLES.get(code, "Task"),
                "status": TaskStatus.DONE,
                "completed_at": ts,
            },
        )

        # Newly created and already DONE => still emit TASK_DONE once
        if created:
            emit_event(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=encounter_id,
                event_key=f"TASK_DONE:{task.id}",
                code="TASK_DONE",
                title="Task completed",
                timestamp=task.completed_at or ts,
                meta={
                    "task_id": str(task.id),
                    "task_code": task.code,
                    "task_title": task.title,
                    "status": task.status,
                    "assigned_to_id": task.assigned_to_id,
                },
            )
            return 1

        if task.status == TaskStatus.DONE and task.completed_at:
            return 0

        task.status = TaskStatus.DONE
        task.completed_at = task.completed_at or ts

        update_fields = ["status", "completed_at"]
        TaskService._touch_updated_at(task, update_fields)
        task.save(update_fields=update_fields)

        emit_event(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            event_key=f"TASK_DONE:{task.id}",
            code="TASK_DONE",
            title="Task completed",
            timestamp=task.completed_at,
            meta={
                "task_id": str(task.id),
                "task_code": task.code,
                "task_title": task.title,
                "status": task.status,
                "assigned_to_id": task.assigned_to_id,
            },
        )
        return 1

    @staticmethod
    @transaction.atomic
    def mark_done(*, tenant_id: UUID, facility_id: UUID, encounter_id: UUID, code: str) -> int:
        """
        Backward-compatible alias.

        Existing encounters code/tests call TaskService.mark_done(tenant_id, facility_id, encounter_id, code).
        We keep it to avoid touching encounters right now.

        This is intentionally the BACKFILL/REPAIR behavior (does not enforce workflow).
        """
        return TaskService.backfill_mark_done(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            code=code,
        )

    @staticmethod
    @transaction.atomic
    def close_all_for_encounter(*, tenant_id: UUID, facility_id: UUID, encounter_id: UUID) -> int:
        """
        Completes all tasks for the encounter that are not DONE/CANCELLED.

        Uses strict completion semantics:
        - OPEN tasks are started then completed
        - IN_PROGRESS tasks are completed
        - CANCELLED tasks are left as-is
        """
        count = 0
        qs = Task.objects.select_for_update().filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
        )

        for t in qs:
            if t.status in {TaskStatus.DONE, TaskStatus.CANCELLED}:
                continue

            if t.status == TaskStatus.OPEN:
                TaskService.start_task(tenant_id=tenant_id, facility_id=facility_id, task_id=t.id)

            TaskService.complete_task(tenant_id=tenant_id, facility_id=facility_id, task_id=t.id)
            count += 1

        return count
