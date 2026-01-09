# backend/hm_core/orders/selectors.py
from __future__ import annotations

from django.db.models import QuerySet

from hm_core.orders.models import Order


class OrderSelector:
    class NotFound(Exception):
        pass

    @staticmethod
    def get_order(*, tenant_id, facility_id, order_id) -> Order:
        try:
            return (
                Order.objects.select_related("encounter")
                .prefetch_related("items")
                .get(id=order_id, tenant_id=tenant_id, facility_id=facility_id)
            )
        except Order.DoesNotExist:
            raise OrderSelector.NotFound()

    @staticmethod
    def list_orders(*, tenant_id, facility_id, encounter_id=None) -> QuerySet[Order]:
        qs = (
            Order.objects.filter(tenant_id=tenant_id, facility_id=facility_id)
            .select_related("encounter")
            .prefetch_related("items")
            .order_by("-created_at")
        )
        if encounter_id:
            qs = qs.filter(encounter_id=encounter_id)
        return qs
