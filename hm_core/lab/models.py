# backend/hm_core/lab/models.py

from django.conf import settings
from django.db import models
from hm_core.common.models import ScopedModel
from hm_core.orders.models import OrderItem
from hm_core.encounters.models import Encounter


class LabSample(ScopedModel):
    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name="lab_sample")
    barcode = models.CharField(max_length=64, blank=True, null=True)
    received_at = models.DateTimeField(blank=True, null=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        db_table = "lab_sample"
        indexes = [models.Index(fields=["tenant_id", "facility_id", "order_item"])]


class LabResult(ScopedModel):
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="lab_results")
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="lab_results")

    version = models.PositiveIntegerField()
    result_payload = models.JSONField(default=dict)

    is_critical = models.BooleanField(default=False)
    critical_reasons = models.JSONField(default=list, blank=True)

    verified_at = models.DateTimeField(blank=True, null=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="verified_lab_results")

    released_at = models.DateTimeField(blank=True, null=True)
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="released_lab_results")

    class Meta:
        db_table = "lab_result"
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "order_item"]),
            models.Index(fields=["tenant_id", "facility_id", "encounter"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["tenant_id", "facility_id", "order_item", "version"], name="uq_lab_result_version_per_item_scope")
        ]
