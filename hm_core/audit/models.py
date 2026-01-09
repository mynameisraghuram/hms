# backend/hm_core/audit/models.py
from django.conf import settings
from django.db import models
from hm_core.common.models import ScopedModel


class AuditEvent(ScopedModel):
    """
    Immutable audit record.
    In healthcare workflows, this becomes your ground-truth timeline.
    """
    event_code = models.CharField(max_length=128, db_index=True)  # e.g. "encounter.closed"
    entity_type = models.CharField(max_length=128, db_index=True)  # e.g. "Encounter"
    entity_id = models.UUIDField(db_index=True)

    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audit_events",
        null=True,
        blank=True,
    )

    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "audit_audit_event"
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "occurred_at"]),
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["tenant_id", "facility_id", "event_code"]),
        ]
