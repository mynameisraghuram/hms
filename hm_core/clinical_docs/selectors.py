# backend/hm_core/clinical_docs/selectors.py
from __future__ import annotations

from uuid import UUID

from django.db.models import QuerySet

from hm_core.clinical_docs.models import ClinicalDocument, EncounterDocument


class ClinicalDocSelectors:
    # ---------- Phase-0 ----------
    @staticmethod
    def encounter_docs_qs(*, tenant_id: UUID, facility_id: UUID, encounter_id: UUID) -> QuerySet[EncounterDocument]:
        return EncounterDocument.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
        ).order_by("-authored_at", "-created_at")

    # ---------- Phase-1 ----------
    @staticmethod
    def get_document(*, tenant_id: UUID, facility_id: UUID, document_id: UUID) -> ClinicalDocument:
        return ClinicalDocument.objects.get(id=document_id, tenant_id=tenant_id, facility_id=facility_id)
