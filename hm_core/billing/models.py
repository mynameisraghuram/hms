#backend\hm_core\billing\models.py
from django.db import models
from hm_core.common.models import ScopedModel
from hm_core.encounters.models import Encounter
from hm_core.orders.models import OrderItem


class EventType(models.TextChoices):
    SERVICE_DELIVERED = "SERVICE_DELIVERED", "Service Delivered"


class BillableEvent(ScopedModel):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="billable_events")
    source_order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name="billable_event")

    event_type = models.CharField(max_length=32, choices=EventType.choices, default=EventType.SERVICE_DELIVERED)
    chargeable_code = models.SlugField(max_length=64)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "billing_billable_event"
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "encounter"]),
        ]
