from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence
from uuid import UUID

from django.db.models import Max, Q

from hm_core.clinical_docs.models import ClinicalDocument, DocumentStatus


@dataclass(frozen=True)
class LatestClinicalDocsRow:
    """
    Kept as a stable read-model shape. Not strictly needed by these tests,
    but exported because tests import it.
    """
    tenant_id: UUID
    facility_id: UUID
    encounter_id: UUID
    patient_id: Optional[UUID]
    template_code: str
    id: UUID
    version: int
    status: str


def latest_documents_per_template_for_encounter(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    encounter_id: UUID,
    statuses: Optional[Sequence[str]] = None,
) -> Iterable[ClinicalDocument]:
    """
    Return the latest ClinicalDocument per template_code for a single encounter,
    constrained by (tenant_id, facility_id, encounter_id), and filtered by status.

    Defaults: FINAL + AMENDED (draft excluded).
    Picks highest version per template_code.
    """
    if statuses is None:
        statuses = (DocumentStatus.FINAL, DocumentStatus.AMENDED)

    base = ClinicalDocument.objects.filter(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter_id,
        status__in=statuses,
    )

    # For each template_code, find max(version)
    latest_versions = (
        base.values("template_code")
        .annotate(max_version=Max("version"))
        .values("template_code", "max_version")
    )

    # Build OR query: (template_code=A AND version=maxA) OR (template_code=B AND version=maxB) ...
    q = Q()
    pairs = list(latest_versions)
    for row in pairs:
        q |= Q(template_code=row["template_code"], version=row["max_version"])

    if not pairs:
        return ClinicalDocument.objects.none()

    # Return actual ClinicalDocument rows matching those latest pairs, within same scope/status set.
    # If somehow ties exist (same template_code+version duplicates), ordering makes output deterministic.
    return (
        base.filter(q)
        .order_by("template_code", "-version", "-created_at")
    )


def latest_document_for_template(
    *,
    tenant_id: UUID,
    facility_id: UUID,
    encounter_id: UUID,
    template_code: str,
    statuses: Optional[Sequence[str]] = None,
) -> Optional[ClinicalDocument]:
    """
    Return the single latest document for a template within scope, by highest version.
    Defaults: FINAL + AMENDED.
    """
    if statuses is None:
        statuses = (DocumentStatus.FINAL, DocumentStatus.AMENDED)

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
    statuses: Optional[Sequence[str]] = None,
) -> list[LatestClinicalDocsRow]:
    """
    Convenience wrapper returning dataclass rows. Not used by your current test file,
    but exported and useful for future list endpoints.
    """
    docs = latest_documents_per_template_for_encounter(
        tenant_id=tenant_id,
        facility_id=facility_id,
        encounter_id=encounter_id,
        statuses=statuses,
    )

    return [
        LatestClinicalDocsRow(
            tenant_id=d.tenant_id,
            facility_id=d.facility_id,
            encounter_id=d.encounter_id,
            patient_id=getattr(d, "patient_id", None),
            template_code=d.template_code,
            id=d.id,
            version=d.version,
            status=d.status,
        )
        for d in docs
    ]
