# backend/hm_core/orders/models.py
from django.db import models
from hm_core.common.models import ScopedModel
from hm_core.encounters.models import Encounter


class OrderType(models.TextChoices):
    LAB = "LAB", "Lab"


class OrderPriority(models.TextChoices):
    ROUTINE = "ROUTINE", "Routine"
    URGENT = "URGENT", "Urgent"
    STAT = "STAT", "Stat"


class OrderStatus(models.TextChoices):
    CREATED = "CREATED", "Created"
    CANCELLED = "CANCELLED", "Cancelled"


class OrderItemStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Requested"


class Order(ScopedModel):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="orders")
    order_type = models.CharField(max_length=16, choices=OrderType.choices)
    priority = models.CharField(max_length=16, choices=OrderPriority.choices, default=OrderPriority.ROUTINE)
    status = models.CharField(max_length=16, choices=OrderStatus.choices, default=OrderStatus.CREATED)

    class Meta:
        db_table = "orders_order"
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "encounter"]),
        ]


class OrderItem(ScopedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="order_items")
    service_code = models.SlugField(max_length=64)
    priority = models.CharField(max_length=16, choices=OrderPriority.choices, default=OrderPriority.ROUTINE)
    status = models.CharField(max_length=16, choices=OrderItemStatus.choices, default=OrderItemStatus.REQUESTED)

    class Meta:
        db_table = "orders_order_item"
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "encounter"]),
            models.Index(fields=["tenant_id", "facility_id", "order"]),
        ]
