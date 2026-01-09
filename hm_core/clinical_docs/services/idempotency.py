#backend\hm_core\clinical_docs\services\idempotency.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from hm_core.clinical_docs.models import ClinicalDocument, DocumentStatus


def normalize_idempotency_key(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip()
    return v if v else None


def get_key_from_request(request) -> Optional[str]:
    """
    Prefer header "Idempotency-Key". In Django META it's HTTP_IDEMPOTENCY_KEY.
    Fallback to request body field if present.
    """
    raw = request.META.get("HTTP_IDEMPOTENCY_KEY") or request.data.get("idempotency_key")
    return normalize_idempotency_key(raw)


def find_draft(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    encounter_id: UUID,
    template_code: str,
    idempotency_key: Optional[str],
) -> Optional[ClinicalDocument]:
    idempotency_key = normalize_idempotency_key(idempotency_key)
    if not idempotency_key:
        return None
    return (
        ClinicalDocument.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            template_code=template_code,
            status=DocumentStatus.DRAFT,
            idempotency_key=idempotency_key,
        )
        .order_by("created_at")
        .first()
    )


def find_finalize(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    supersedes_document_id: UUID,
    idempotency_key: Optional[str],
) -> Optional[ClinicalDocument]:
    idempotency_key = normalize_idempotency_key(idempotency_key)
    if not idempotency_key:
        return None
    return (
        ClinicalDocument.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            supersedes_document_id=supersedes_document_id,
            status=DocumentStatus.FINAL,
            idempotency_key=idempotency_key,
        )
        .order_by("created_at")
        .first()
    )


def find_amend(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    supersedes_document_id: UUID,
    idempotency_key: Optional[str],
) -> Optional[ClinicalDocument]:
    idempotency_key = normalize_idempotency_key(idempotency_key)
    if not idempotency_key:
        return None
    return (
        ClinicalDocument.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            supersedes_document_id=supersedes_document_id,
            status=DocumentStatus.AMENDED,
            idempotency_key=idempotency_key,
        )
        .order_by("created_at")
        .first()
    )
