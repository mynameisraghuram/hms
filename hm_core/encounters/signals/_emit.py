# hm_core/encounters/signals/_emit.py
from __future__ import annotations

from typing import Any, Dict, Optional

from django.utils.timezone import now

from hm_core.encounters.models import EncounterEvent


def emit_event(
    *,
    tenant_id,
    facility_id,
    encounter_id,
    event_key: str,
    code: str,
    title: str = "",
    timestamp=None,
    meta: Optional[Dict[str, Any]] = None,
):
    """
    Idempotent, transaction-safe event write.

    IMPORTANT:
    - In tests (pytest + django_db), on_commit callbacks often never run because the
      test is wrapped in a transaction that rolls back instead of committing.
    - Writing the event inside the same DB transaction is safe: if the transaction
      rolls back, the event row rolls back too (no "ghost history").

    So we write immediately (still idempotent via event_key uniqueness).
    """
    if timestamp is None:
        timestamp = now()
    if meta is None:
        meta = {}

    EncounterEvent.objects.get_or_create(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter_id,
        event_key=event_key,
        defaults={
            "type": "EVENT",
            "code": code,
            "title": title,
            "timestamp": timestamp,
            "meta": meta,
        },
    )
