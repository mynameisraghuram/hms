# backend/hm_core/encounters/rules.py
from __future__ import annotations

from uuid import UUID

from rest_framework.exceptions import ValidationError

from hm_core.tasks.models import Task, TaskStatus


class EncounterRuleEngine:
    """
    Encounter-specific rules implementation.

    IMPORTANT:
    - Canonical close-gate (docs/tasks) lives in: hm_core.rules.engine.RuleEngine
    - This module is kept ONLY for encounter-specific hard safety blockers
      (critical ack) to avoid circular imports / cross-app coupling.
    """

    @staticmethod
    def enforce_critical_ack_gate(*, tenant_id: UUID, facility_id: UUID, encounter_id: UUID) -> None:
        """
        Hard safety blocker:
        If a critical-result-ack task exists and is not DONE, closing must be blocked.
        """
        exists_unacked = Task.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            code="critical-result-ack",
        ).exclude(status=TaskStatus.DONE).exists()

        if exists_unacked:
            raise ValidationError(
                {
                    "ok": False,
                    "can_close": False,
                    "detail": "Encounter close blocked by close-gate rules.",
                    "missing": [
                        {"type": "CRITICAL_ACK", "open": ["critical-result-ack"]},
                    ],
                }
            )
