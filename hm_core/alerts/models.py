from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from hm_core.common.models import ScopedModel


class AlertSeverity(models.TextChoices):
    INFO = "INFO", "Info"
    WARNING = "WARNING", "Warning"
    CRITICAL = "CRITICAL", "Critical"


class AlertStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    ACKED = "ACKED", "Acknowledged"
    RESOLVED = "RESOLVED", "Resolved"
    DISMISSED = "DISMISSED", "Dismissed"


class Alert(ScopedModel):
    """
    Trackable alert visible in UI (worklist companion, NOT a replacement for Task).
    Keep links loose (UUID fields) to avoid cross-app FK coupling.
    """
    code = models.SlugField(max_length=64, db_index=True)  # e.g. "critical-lab-result"
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True, default="")

    severity = models.CharField(
        max_length=16,
        choices=AlertSeverity.choices,
        default=AlertSeverity.INFO,
        db_index=True,
    )
    status = models.CharField(
        max_length=16,
        choices=AlertStatus.choices,
        default=AlertStatus.OPEN,
        db_index=True,
    )

    encounter_id = models.UUIDField(null=True, blank=True, db_index=True)
    task_id = models.UUIDField(null=True, blank=True, db_index=True)
    patient_id = models.UUIDField(null=True, blank=True, db_index=True)
    lab_result_id = models.UUIDField(null=True, blank=True, db_index=True)

    created_by_user_id = models.IntegerField(null=True, blank=True)
    acked_by_user_id = models.IntegerField(null=True, blank=True)
    acked_at = models.DateTimeField(null=True, blank=True)

    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "status", "severity"]),
            models.Index(fields=["tenant_id", "facility_id", "encounter_id"]),
            models.Index(fields=["tenant_id", "facility_id", "task_id"]),
        ]


class NotificationChannel(models.TextChoices):
    IN_APP = "IN_APP", "In App"
    EMAIL = "EMAIL", "Email"
    SMS = "SMS", "SMS"
    WHATSAPP = "WHATSAPP", "WhatsApp"


class Notification(ScopedModel):
    """
    Delivery records per user. Phase-1: IN_APP only. Others reserved for later.
    """
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    channel = models.CharField(
        max_length=16,
        choices=NotificationChannel.choices,
        default=NotificationChannel.IN_APP,
        db_index=True,
    )

    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")

    alert = models.ForeignKey(
        Alert,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )

    encounter_id = models.UUIDField(null=True, blank=True, db_index=True)
    task_id = models.UUIDField(null=True, blank=True, db_index=True)

    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    meta = models.JSONField(default=dict, blank=True)

    def mark_read(self) -> None:
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
