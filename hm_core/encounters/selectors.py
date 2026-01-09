# backend/hm_core/encounters/selectors.py
from __future__ import annotations

from uuid import UUID

from hm_core.encounters.models import EncounterEvent


class EncounterSelectors:
    """
    Read-only queries for encounters.
    No .save(), no state mutation here.
    """

    @staticmethod
    def timeline_items(*, tenant_id: UUID, facility_id: UUID, encounter_id: UUID) -> list[dict]:
        events = (
            EncounterEvent.objects.filter(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=encounter_id,
            )
            .order_by("timestamp", "created_at")
        )

        items: list[dict] = []
        for e in events:
            at = getattr(e, "timestamp", None) or getattr(e, "created_at", None)
            items.append(
                {
                    "type": "EVENT",
                    "id": str(e.id),
                    "code": e.code,
                    "title": getattr(e, "title", "") or "",
                    "at": at,
                    "meta": getattr(e, "meta", None) or {},
                }
            )
        return items
