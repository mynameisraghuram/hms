# backend/hm_core/orders/services.py
from __future__ import annotations

from uuid import UUID

from django.db import transaction

from hm_core.common.task_codes import lab_result_enter_code, lab_sample_receive_code
from hm_core.encounters.models import Encounter
from hm_core.orders.models import Order, OrderItem, OrderPriority
from hm_core.tasks.services import TaskService


class OrderService:
    """
    Write-model operations for Orders.
    - Creates Order + OrderItems atomically
    - Creates the per-item lab tasks (idempotent) via TaskService
    """

    @staticmethod
    @transaction.atomic
    def create_order(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        encounter_id: UUID,
        order_type: str,
        priority: str | None,
        items: list[dict],
    ) -> tuple[Order, list[OrderItem]]:
        encounter = Encounter.objects.get(id=encounter_id, tenant_id=tenant_id, facility_id=facility_id)

        order = Order.objects.create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter=encounter,
            order_type=order_type,
            priority=priority or OrderPriority.ROUTINE,
        )

        items_out: list[OrderItem] = []
        for item in items:
            oi = OrderItem.objects.create(
                tenant_id=tenant_id,
                facility_id=facility_id,
                order=order,
                encounter=encounter,
                service_code=item["service_code"],
                priority=item.get("priority") or order.priority,
            )
            items_out.append(oi)

            # Per-item tasks (idempotent on encounter+code)
            TaskService.create_task(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=encounter.id,
                code=lab_sample_receive_code(oi.id),
                title="Receive Lab Sample",
            )
            TaskService.create_task(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=encounter.id,
                code=lab_result_enter_code(oi.id),
                title="Enter Lab Result",
            )

        return order, items_out
