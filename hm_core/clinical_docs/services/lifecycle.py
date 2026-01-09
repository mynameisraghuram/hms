#backend\hm_core\clinical_docs\services\lifecycle.py
from __future__ import annotations

from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import Max

from hm_core.clinical_docs.models import ClinicalDocument, DocumentStatus
from hm_core.clinical_docs.services.idempotency import (
    find_amend,
    find_draft,
    find_finalize,
    normalize_idempotency_key,
)


def _next_version(*, encounter_id: UUID, template_code: str) -> int:
    mx = (
        ClinicalDocument.objects.filter(
            encounter_id=encounter_id,
            template_code=template_code,
        ).aggregate(m=Max("version"))["m"]
        or 0
    )
    return int(mx) + 1


@transaction.atomic
def create_draft(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    patient_id: UUID,
    encounter_id: UUID,
    template_code: str,
    payload: dict,
    created_by_user_id: int,
    idempotency_key: str | None,
) -> tuple[ClinicalDocument, bool]:
    idempotency_key = normalize_idempotency_key(idempotency_key)

    existing = find_draft(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter_id,
        template_code=template_code,
        idempotency_key=idempotency_key,
    )
    if existing:
        return existing, False

    version = _next_version(encounter_id=encounter_id, template_code=template_code)

    try:
        doc = ClinicalDocument.objects.create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            template_code=template_code,
            version=version,
            status=DocumentStatus.DRAFT,
            payload=payload or {},
            idempotency_key=idempotency_key,
            created_by_user_id=int(created_by_user_id),
        )
        return doc, True
    except IntegrityError:
        # Retry storm protection: if another txn won first, fetch and return it.
        existing = find_draft(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            template_code=template_code,
            idempotency_key=idempotency_key,
        )
        if existing:
            return existing, False
        raise


@transaction.atomic
def finalize(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    document_id: UUID,
    created_by_user_id: int,
    idempotency_key: str | None,
) -> tuple[ClinicalDocument, bool]:
    idempotency_key = normalize_idempotency_key(idempotency_key)

    base = ClinicalDocument.objects.select_for_update().get(
        id=document_id,
        tenant_id=tenant_id,
        facility_id=facility_id,
    )
    if base.status != DocumentStatus.DRAFT:
        raise ValueError(f"Only DRAFT can be finalized (current={base.status}).")

    existing = find_finalize(
        tenant_id=tenant_id,
        facility_id=facility_id,
        supersedes_document_id=base.id,
        idempotency_key=idempotency_key,
    )
    if existing:
        return existing, False

    version = _next_version(encounter_id=base.encounter_id, template_code=base.template_code)

    try:
        doc = ClinicalDocument.objects.create(
            tenant_id=base.tenant_id,
            facility_id=base.facility_id,
            patient_id=base.patient_id,
            encounter_id=base.encounter_id,
            template_code=base.template_code,
            version=version,
            status=DocumentStatus.FINAL,
            supersedes_document_id=base.id,
            payload=base.payload,
            idempotency_key=idempotency_key,
            created_by_user_id=int(created_by_user_id),
        )
        return doc, True
    except IntegrityError:
        existing = find_finalize(
            tenant_id=tenant_id,
            facility_id=facility_id,
            supersedes_document_id=base.id,
            idempotency_key=idempotency_key,
        )
        if existing:
            return existing, False
        raise


@transaction.atomic
def amend(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    document_id: UUID,
    payload_patch: dict,
    created_by_user_id: int,
    idempotency_key: str | None,
) -> tuple[ClinicalDocument, bool]:
    idempotency_key = normalize_idempotency_key(idempotency_key)

    base = ClinicalDocument.objects.select_for_update().get(
        id=document_id,
        tenant_id=tenant_id,
        facility_id=facility_id,
    )
    if base.status != DocumentStatus.FINAL:
        raise ValueError(f"Only FINAL can be amended (current={base.status}).")

    existing = find_amend(
        tenant_id=tenant_id,
        facility_id=facility_id,
        supersedes_document_id=base.id,
        idempotency_key=idempotency_key,
    )
    if existing:
        return existing, False

    new_payload = dict(base.payload or {})
    if isinstance(payload_patch, dict):
        new_payload.update(payload_patch)

    version = _next_version(encounter_id=base.encounter_id, template_code=base.template_code)

    try:
        doc = ClinicalDocument.objects.create(
            tenant_id=base.tenant_id,
            facility_id=base.facility_id,
            patient_id=base.patient_id,
            encounter_id=base.encounter_id,
            template_code=base.template_code,
            version=version,
            status=DocumentStatus.AMENDED,
            supersedes_document_id=base.id,
            payload=new_payload,
            idempotency_key=idempotency_key,
            created_by_user_id=int(created_by_user_id),
        )
        return doc, True
    except IntegrityError:
        existing = find_amend(
            tenant_id=tenant_id,
            facility_id=facility_id,
            supersedes_document_id=base.id,
            idempotency_key=idempotency_key,
        )
        if existing:
            return existing, False
        raise
