# backend/hm_core/patients/selectors.py
from __future__ import annotations

from uuid import UUID

from django.db.models import Q, QuerySet

from hm_core.patients.models import Patient


def get_patient(*, tenant_id: UUID, facility_id: UUID, patient_id: UUID) -> Patient:
    return Patient.objects.get(id=patient_id, tenant_id=tenant_id, facility_id=facility_id)


def search_patients(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    q: str | None = None,
) -> QuerySet[Patient]:
    qs = Patient.objects.filter(tenant_id=tenant_id, facility_id=facility_id)

    qv = (q or "").strip()
    if qv:
        qs = qs.filter(
            Q(full_name__icontains=qv)
            | Q(mrn__icontains=qv)
            | Q(phone__icontains=qv)
            | Q(email__icontains=qv)
        )

    return qs.order_by("-created_at")
