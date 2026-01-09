# backend/hm_core/audit/selectors.py
from __future__ import annotations

from uuid import UUID

from django.db.models import QuerySet

from hm_core.audit.models import AuditEvent


def list_audit_events(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    event_code: str | None = None,
    actor_user_id: int | None = None,
) -> QuerySet[AuditEvent]:
    qs = AuditEvent.objects.filter(tenant_id=tenant_id, facility_id=facility_id)

    if entity_type:
        qs = qs.filter(entity_type=entity_type)
    if entity_id:
        qs = qs.filter(entity_id=entity_id)
    if event_code:
        qs = qs.filter(event_code=event_code)
    if actor_user_id is not None:
        qs = qs.filter(actor_user_id=actor_user_id)

    return qs.order_by("-occurred_at")
