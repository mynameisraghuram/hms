# backend/hm_core/lab/selectors.py
from __future__ import annotations

from uuid import UUID

from hm_core.orders.models import OrderItem
from hm_core.lab.models import LabResult


def get_order_item_scoped(*, tenant_id: UUID, facility_id: UUID, order_item_id: UUID) -> OrderItem:
    return OrderItem.objects.get(id=order_item_id, tenant_id=tenant_id, facility_id=facility_id)


def latest_result_for_item(*, tenant_id: UUID, facility_id: UUID, order_item_id: UUID) -> LabResult | None:
    return (
        LabResult.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            order_item_id=order_item_id,
        )
        .order_by("-version")
        .first()
    )
