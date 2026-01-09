from __future__ import annotations

from uuid import UUID
from django.db.models import QuerySet

from hm_core.alerts.models import Alert, Notification


def alerts_qs(*, tenant_id: UUID, facility_id: UUID) -> QuerySet[Alert]:
    return Alert.objects.filter(tenant_id=tenant_id, facility_id=facility_id)


def notifications_qs(*, tenant_id: UUID, facility_id: UUID, user_id: int) -> QuerySet[Notification]:
    return Notification.objects.filter(
        tenant_id=tenant_id,
        facility_id=facility_id,
        recipient_id=user_id,
        channel="IN_APP",
    )
