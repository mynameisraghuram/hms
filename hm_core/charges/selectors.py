from __future__ import annotations

from uuid import UUID

from hm_core.charges.models import ChargeItem


def get_active_charge_item(*, tenant_id: UUID, facility_id: UUID, code: str) -> ChargeItem | None:
    return (
        ChargeItem.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            code=code,
            is_active=True,
        )
        .order_by("-created_at")
        .first()
    )
