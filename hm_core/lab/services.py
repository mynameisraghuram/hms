# backend/hm_core/lab/services.py
from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.utils import timezone

from hm_core.common.task_codes import (
    lab_sample_receive_code,
    lab_result_enter_code,
    lab_result_verify_code,
    critical_ack_code,
)
from hm_core.lab.models import LabSample, LabResult
from hm_core.lab.selectors import get_order_item_scoped, latest_result_for_item
from hm_core.tasks.services import TaskService
from hm_core.billing.models import BillableEvent


def _critical_check(result_payload: dict) -> tuple[bool, list[dict]]:
    """
    Phase-1 minimal rule: hb < 6 => critical
    """
    reasons: list[dict] = []
    hb = (result_payload or {}).get("hb")
    try:
        if hb is not None and float(hb) < 6.0:
            reasons.append({"code": "HB_LOW", "value": hb, "threshold": 6.0})
    except Exception:
        pass
    return (len(reasons) > 0), reasons


class LabService:
    """
    Write-model operations for Lab module.
    - Receive sample (idempotent via get_or_create)
    - Create lab result version (append-only versioning)
    - Verify latest result only
    - Release (requires verification, emits billing event once)
    """

    # ----------------------------
    # Sample receive
    # ----------------------------
    @staticmethod
    @transaction.atomic
    def receive_sample(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        order_item_id: UUID,
        actor_user,
        barcode: str | None,
    ) -> LabSample:
        oi = get_order_item_scoped(tenant_id=tenant_id, facility_id=facility_id, order_item_id=order_item_id)

        sample, created = LabSample.objects.get_or_create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            order_item=oi,
            defaults={
                "barcode": barcode or None,
                "received_at": timezone.now(),
                "received_by": actor_user,
            },
        )

        if not created:
            changed = False
            if barcode and sample.barcode != barcode:
                sample.barcode = barcode
                changed = True
            if not sample.received_at:
                sample.received_at = timezone.now()
                changed = True
            if not sample.received_by_id:
                sample.received_by = actor_user
                changed = True
            if changed:
                sample.save()

        # Mark "receive sample" task DONE (backfill semantics; avoids strict workflow requirement)
        TaskService.backfill_mark_done(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=oi.encounter_id,
            code=lab_sample_receive_code(oi.id),
        )

        return sample

    # ----------------------------
    # Create lab result (new version)
    # ----------------------------
    @staticmethod
    @transaction.atomic
    def create_result(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        order_item_id: UUID,
        result_payload: dict,
    ) -> LabResult:
        oi = get_order_item_scoped(tenant_id=tenant_id, facility_id=facility_id, order_item_id=order_item_id)

        latest = latest_result_for_item(tenant_id=tenant_id, facility_id=facility_id, order_item_id=oi.id)
        next_version = 1 if not latest else int(latest.version) + 1

        is_critical, reasons = _critical_check(result_payload or {})

        lr = LabResult.objects.create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            order_item=oi,
            encounter=oi.encounter,
            version=next_version,
            result_payload=result_payload or {},
            is_critical=is_critical,
            critical_reasons=reasons,
        )

        # Mark "enter lab result" DONE (backfill semantics)
        TaskService.backfill_mark_done(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=oi.encounter_id,
            code=lab_result_enter_code(oi.id),
        )

        # Create verify task (idempotent create; emits TASK_CREATED once)
        TaskService.create_task(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=oi.encounter_id,
            code=lab_result_verify_code(oi.id),
            title="Verify Lab Result",
        )

        # Critical => create ack task (single code for encounter)
        if lr.is_critical:
            TaskService.create_task(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=oi.encounter_id,
                code=critical_ack_code(),  # "critical-result-ack"
                title="Acknowledge Critical Result",
            )

        return lr

    # ----------------------------
    # Verify (latest only)
    # ----------------------------
    @staticmethod
    @transaction.atomic
    def verify_result(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        lab_result_id: UUID,
        actor_user,
    ) -> LabResult:
        lr = LabResult.objects.select_for_update().get(id=lab_result_id, tenant_id=tenant_id, facility_id=facility_id)

        latest = latest_result_for_item(
            tenant_id=tenant_id,
            facility_id=facility_id,
            order_item_id=lr.order_item_id,
        )
        if latest and latest.id != lr.id:
            raise ValueError("Only latest version can be verified")

        if not lr.verified_at:
            lr.verified_at = timezone.now()
            lr.verified_by = actor_user
            lr.save(update_fields=["verified_at", "verified_by", "updated_at"])

            TaskService.backfill_mark_done(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=lr.encounter_id,
                code=lab_result_verify_code(lr.order_item_id),
            )

        return lr

    # ----------------------------
    # Release (requires verification)
    # ----------------------------
    @staticmethod
    @transaction.atomic
    def release_result(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        lab_result_id: UUID,
        actor_user,
    ) -> LabResult:
        lr = LabResult.objects.select_for_update().get(id=lab_result_id, tenant_id=tenant_id, facility_id=facility_id)

        if not lr.verified_at:
            raise ValueError("Verification required before release")

        if not lr.released_at:
            lr.released_at = timezone.now()
            lr.released_by = actor_user
            lr.save(update_fields=["released_at", "released_by", "updated_at"])

        # Billing event exactly once
        BillableEvent.objects.get_or_create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter=lr.encounter,
            source_order_item=lr.order_item,
            defaults={"chargeable_code": lr.order_item.service_code, "quantity": 1},
        )

        # Backup: ensure ACK task exists if critical
        if lr.is_critical:
            TaskService.create_task(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=lr.encounter_id,
                code=critical_ack_code(),
                title="Acknowledge Critical Result",
            )

        return lr
