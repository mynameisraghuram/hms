from __future__ import annotations
from uuid import UUID

def maybe_create_alerts_for_task_created(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    actor_user_id: int | None,
    task,
) -> None:
    if getattr(task, "code", None) != "critical-result-ack":
        return

    from hm_core.alerts.services import AlertContext, AlertService, NotificationService
    from hm_core.alerts.models import AlertSeverity

    ctx = AlertContext(tenant_id=tenant_id, facility_id=facility_id, actor_user_id=actor_user_id)

    alert = AlertService.create_alert(
        ctx=ctx,
        code="critical-lab-result",
        title="Critical lab result requires acknowledgement",
        message=getattr(task, "title", "") or "Critical result acknowledgement required",
        severity=AlertSeverity.CRITICAL,
        encounter_id=getattr(task, "encounter_id", None),
        task_id=getattr(task, "id", None),
        meta={"task_code": getattr(task, "code", None)},
    )

    assigned_to_id = getattr(task, "assigned_to_id", None)
    if assigned_to_id:
        NotificationService.notify_users_in_app(
            ctx=ctx,
            user_ids=[assigned_to_id],
            title=alert.title,
            body=alert.message,
            alert=alert,
            encounter_id=getattr(task, "encounter_id", None),
            task_id=getattr(task, "id", None),
        )
