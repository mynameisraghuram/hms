# backend/hm_core/tasks/selectors.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now

from hm_core.tasks.models import Task


class TaskSelector:
    class NotFound(Exception):
        pass

    @staticmethod
    def get_task(*, tenant_id, facility_id, task_id) -> Task:
        try:
            return Task.objects.get(id=task_id, tenant_id=tenant_id, facility_id=facility_id)
        except Task.DoesNotExist:
            raise TaskSelector.NotFound()

    @staticmethod
    def list_tasks(*, tenant_id, facility_id, user_id: Optional[int], params: Any) -> QuerySet[Task]:
        """
        Query params supported (same behavior as your existing view):
          - encounter or encounter_id
          - status
          - assigned_to_id
          - mine=1|true
          - overdue=1|true
          - due_before=ISO datetime
          - due_after=ISO datetime
          - ordering in {created_at, -created_at, due_at, -due_at}
        """
        encounter_id = params.get("encounter_id") or params.get("encounter")
        status_param = params.get("status")
        assigned_to_id = params.get("assigned_to_id")
        overdue = params.get("overdue")
        due_before = params.get("due_before")
        due_after = params.get("due_after")
        ordering = params.get("ordering")
        mine = params.get("mine")

        qs = Task.objects.filter(tenant_id=tenant_id, facility_id=facility_id)

        if encounter_id:
            qs = qs.filter(encounter_id=encounter_id)

        if status_param:
            qs = qs.filter(status=status_param)

        if assigned_to_id:
            qs = qs.filter(assigned_to_id=assigned_to_id)

        if mine in {"1", "true", "True"}:
            if not user_id:
                raise ValidationError("mine=1 requires an authenticated user.")
            qs = qs.filter(assigned_to_id=user_id)

        if overdue in {"1", "true", "True"}:
            qs = qs.filter(due_at__lt=now()).exclude(status__in=["DONE", "CANCELLED"])

        if due_before:
            dt = parse_datetime(due_before)
            if not dt:
                raise ValidationError("due_before is invalid. Use ISO datetime.")
            qs = qs.filter(due_at__lte=dt)

        if due_after:
            dt = parse_datetime(due_after)
            if not dt:
                raise ValidationError("due_after is invalid. Use ISO datetime.")
            qs = qs.filter(due_at__gte=dt)

        allowed = {"created_at", "-created_at", "due_at", "-due_at"}
        if ordering:
            if ordering not in allowed:
                raise ValidationError(f"ordering is invalid. Allowed: {sorted(allowed)}")
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-created_at")

        return qs
