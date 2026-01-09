# backend/hm_core/clinical_docs/services/read_models.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple
from uuid import UUID

from django.db.models import QuerySet

from hm_core.clinical_docs.models import ClinicalDocument, DocumentStatus


# Used by API default behavior (exclude drafts)
DEFAULT_LATEST_STATUSES: Tuple[str, ...] = (
    DocumentStatus.FINAL,
    DocumentStatus.AMENDED,
)


@dataclass(frozen=True)
class LatestClinicalDocsRow:
    """
    Read-model row for "latest docs per encounter/patient" style queries.
    """
    tenant_id: UUID
    facility_id: UUID
    encounter_id: UUID
    doc_type: str  # template_code
    latest_document_id: UUID
    latest_created_at_iso: str
    patient_id: Optional[UUID] = None


def latest_documents_per_template_for_encounter(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    encounter_id: UUID,
    statuses: Tuple[str, ...] = DEFAULT_LATEST_STATUSES,
) -> QuerySet[ClinicalDocument]:
    """
    Return the latest ClinicalDocument per template_code for an encounter.

    Postgres-optimized using DISTINCT ON.
    Ordering rule:
      - highest version wins
      - tie-breaker: newest created_at
    """
    qs = (
        ClinicalDocument.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            status__in=statuses,
        )
        .order_by("template_code", "-version", "-created_at")
    )

    # DISTINCT ON is supported by Django on PostgreSQL only.
    return qs.distinct("template_code")


def latest_document_for_template(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    encounter_id: UUID,
    template_code: str,
    statuses: Tuple[str, ...] = DEFAULT_LATEST_STATUSES,
) -> Optional[ClinicalDocument]:
    """
    Return latest doc for a single template_code (highest version, newest created_at).
    """
    return (
        ClinicalDocument.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            template_code=template_code,
            status__in=statuses,
        )
        .order_by("-version", "-created_at")
        .first()
    )


def build_latest_docs_read_model(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    encounter_id: UUID,
    statuses: Tuple[str, ...] = DEFAULT_LATEST_STATUSES,
) -> Iterable[LatestClinicalDocsRow]:
    """
    Build a simple read-model list from the latest docs per template for an encounter.
    """
    docs = latest_documents_per_template_for_encounter(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter_id,
        statuses=statuses,
    )

    for d in docs:
        yield LatestClinicalDocsRow(
            tenant_id=d.tenant_id,
            facility_id=d.facility_id,
            encounter_id=d.encounter_id,
            patient_id=getattr(d, "patient_id", None),
            doc_type=d.template_code,
            latest_document_id=d.id,
            latest_created_at_iso=d.created_at.isoformat(),
        )
