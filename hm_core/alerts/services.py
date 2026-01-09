from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from hm_core.alerts.models import Alert, AlertSeverity, AlertStatus, Notification


@dataclass(frozen=True)
class AlertContext:
    tenant_id: UUID
    facility_id: UUID
    actor_user_id: int | None


class AlertService:
    @staticmethod
    @transaction.atomic
    def create_alert(
        *,
        ctx: AlertContext,
        code: str,
        title: str,
        message: str = "",
        severity: str = AlertSeverity.INFO,
        encounter_id: UUID | None = None,
        task_id: UUID | None = None,
        patient_id: UUID | None = None,
        lab_result_id: UUID | None = None,
        meta: dict | None = None,
    ) -> Alert:
        return Alert.objects.create(
            tenant_id=ctx.tenant_id,
            facility_id=ctx.facility_id,
            created_by_user_id=ctx.actor_user_id,
            code=code,
            title=title,
            message=message,
            severity=severity,
            status=AlertStatus.OPEN,
            encounter_id=encounter_id,
            task_id=task_id,
            patient_id=patient_id,
            lab_result_id=lab_result_id,
            meta=meta or {},
        )

    @staticmethod
    @transaction.atomic
    def ack_alert(*, ctx: AlertContext, alert_id: UUID) -> Alert:
        alert = Alert.objects.get(id=alert_id, tenant_id=ctx.tenant_id, facility_id=ctx.facility_id)
        if alert.status != AlertStatus.ACKED:
            alert.status = AlertStatus.ACKED
            alert.acked_by_user_id = ctx.actor_user_id
            alert.acked_at = timezone.now()
            alert.save(update_fields=["status", "acked_by_user_id", "acked_at", "updated_at"])
        return alert


class NotificationService:
    @staticmethod
    @transaction.atomic
    def notify_users_in_app(
        *,
        ctx: AlertContext,
        user_ids: Iterable[int],
        title: str,
        body: str = "",
        alert: Alert | None = None,
        encounter_id: UUID | None = None,
        task_id: UUID | None = None,
        meta: dict | None = None,
    ) -> list[Notification]:
        objs = [
            Notification(
                tenant_id=ctx.tenant_id,
                facility_id=ctx.facility_id,
                recipient_id=uid,
                channel="IN_APP",
                title=title,
                body=body,
                alert=alert,
                encounter_id=encounter_id,
                task_id=task_id,
                meta=meta or {},
            )
            for uid in user_ids
        ]
        return Notification.objects.bulk_create(objs)
