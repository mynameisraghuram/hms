# backend/hm_core/audit/services.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID

from django.db import transaction

from hm_core.audit.models import AuditEvent


@dataclass(frozen=True)
class AuditRecord:
    event_code: str
    entity_type: str
    entity_id: UUID
    tenant_id: UUID
    facility_id: UUID
    actor_user_id: int | None
    metadata: Dict[str, Any]


class AuditService:
    """
    Central audit writer.
    Phase 0+: persists into AuditEvent (immutable).
    """

    @staticmethod
    @transaction.atomic
    def log(
        *,
        event_code: str,
        entity_type: str,
        entity_id: UUID,
        tenant_id: UUID,
        facility_id: UUID,
        actor_user_id: int | None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditRecord:
        metadata = metadata or {}

        AuditEvent.objects.create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            event_code=event_code,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor_user_id,  # ✅ int | None
            metadata=metadata,
        )

        return AuditRecord(
            event_code=event_code,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=tenant_id,
            facility_id=facility_id,
            actor_user_id=actor_user_id,
            metadata=metadata,
        )
