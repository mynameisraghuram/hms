# backend/hm_core/billing/selectors.py
from __future__ import annotations

from uuid import UUID

from django.db.models import QuerySet

from hm_core.billing.models import BillableEvent, Invoice


def billable_events_qs(*, tenant_id: UUID, facility_id: UUID) -> QuerySet[BillableEvent]:
    return BillableEvent.objects.filter(tenant_id=tenant_id, facility_id=facility_id)


def billable_events_filtered(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    encounter_id: UUID | None = None,
    patient_id: UUID | None = None,
) -> QuerySet[BillableEvent]:
    qs = billable_events_qs(tenant_id=tenant_id, facility_id=facility_id).order_by("-created_at")

    if encounter_id:
        qs = qs.filter(encounter_id=encounter_id)

    if patient_id:
        qs = qs.filter(encounter__patient_id=patient_id)

    return qs


# -------------------------------------------------------------------
# Invoices
# -------------------------------------------------------------------

def invoices_qs(*, tenant_id: UUID, facility_id: UUID) -> QuerySet[Invoice]:
    return Invoice.objects.filter(tenant_id=tenant_id, facility_id=facility_id)


def invoices_filtered(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    patient_id: UUID | None = None,
    encounter_id: UUID | None = None,
    status: str | None = None,
) -> QuerySet[Invoice]:
    qs = invoices_qs(tenant_id=tenant_id, facility_id=facility_id).order_by("-created_at")

    if patient_id:
        qs = qs.filter(patient_id=patient_id)

    if encounter_id:
        qs = qs.filter(encounter_id=encounter_id)

    if status:
        qs = qs.filter(status=status)

    return qs
