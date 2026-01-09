from __future__ import annotations

from typing import Optional
from uuid import UUID

from django.db.models import QuerySet

from hm_core.rules.models import Rule


def get_active_rule(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    code: str,
) -> Optional[Rule]:
    return (
        Rule.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            code=code,
            is_active=True,
        )
        .order_by("-updated_at")
        .first()
    )


def list_rules(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    active_only: bool = True,
) -> QuerySet[Rule]:
    qs = Rule.objects.filter(
        tenant_id=tenant_id,
        facility_id=facility_id,
    )
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.order_by("code")
