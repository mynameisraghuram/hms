# backend/hm_core/encounters/models.py

from typing import Iterable
from django.conf import settings
from django.db import models
from django.db.models import Q
from hm_core.common.models import ScopedModel
from hm_core.patients.models import Patient
from django.core.exceptions import ValidationError
import uuid

from django.utils import timezone

try:
    # Django 3.1+
    from django.db.models import JSONField
except ImportError:  # pragma: no cover
    from django.contrib.postgres.fields import JSONField  # older Django

class EncounterStatus(models.TextChoices):
    CREATED = "CREATED", "Created"
    CHECKED_IN = "CHECKED_IN", "Checked In"
    IN_CONSULT = "IN_CONSULT", "In Consult"
    CLOSED = "CLOSED", "Closed"
    CANCELLED = "CANCELLED", "Cancelled"


class Encounter(ScopedModel):
    """
    OPD visit container. Everything clinical for Phase 0 hangs off Encounter.
    """
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="encounters")

    status = models.CharField(max_length=32, choices=EncounterStatus.choices, default=EncounterStatus.CREATED, db_index=True)

    scheduled_at = models.DateTimeField(null=True, blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    consult_started_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    reason = models.CharField(max_length=255, blank=True)

    attending_doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="doctor_encounters",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_encounters",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "encounters_encounter"
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "status"]),
            models.Index(fields=["tenant_id", "facility_id", "patient"]),
            models.Index(fields=["tenant_id", "facility_id", "created_at"]),
        ]
        constraints = [
            # Prevent two simultaneous active encounters for the same patient in same facility (Phase 0).
            models.UniqueConstraint(
                fields=["tenant_id", "facility_id", "patient"],
                condition=Q(status__in=[EncounterStatus.CREATED, EncounterStatus.CHECKED_IN, EncounterStatus.IN_CONSULT]),
                name="uq_active_encounter_per_patient_scope",
            ),
        ]

    def __str__(self) -> str:
        return f"Encounter({self.patient_id}, {self.status})"


class EncounterEvent(models.Model):
    """
    Immutable history stream for an encounter.
    Timeline must ONLY read from this table.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant_id = models.UUIDField(db_index=True)
    facility_id = models.UUIDField(db_index=True)
    encounter_id = models.UUIDField(db_index=True)

    # Migration-friendly: default avoids makemigrations prompt
    type = models.CharField(max_length=20, default="EVENT")

    # Stable event identity for idempotency (signals can safely re-fire)
    event_key = models.CharField(max_length=128, db_index=True, blank=False)

    # Semantic info
    code = models.CharField(max_length=64, db_index=True)
    title = models.CharField(max_length=255, blank=True, default="")

    # When it happened
    timestamp = models.DateTimeField(db_index=True)

    # Extra context (task_id, doc_id, status, etc.)
    meta = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "encounters_event"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "facility_id", "encounter_id", "event_key"],
                name="uq_encounterevent_key_per_scope",
            )
        ]
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "encounter_id", "timestamp","created_at","id"]),
        ]

    def __str__(self):
        return f"{self.code} @ {self.timestamp}"
    

    def save(self, *args, **kwargs):
        # UUID PK exists even before first save, so use _state.adding
        if not self._state.adding:
            raise ValidationError("EncounterEvent is immutable and cannot be modified once created.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("EncounterEvent is immutable and cannot be deleted.")
