# backend/hm_core/clinical_docs/models.py
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from hm_core.common.models import ScopedModel
from hm_core.encounters.models import Encounter
from django.db.models import Q

class DocKind(models.TextChoices):
    VITALS = "VITALS", "Vitals"
    ASSESSMENT = "ASSESSMENT", "Assessment"
    PLAN = "PLAN", "Plan"
    NOTE = "NOTE", "Note"


class EncounterDocument(ScopedModel):
    """
    Phase-0: Simple flexible clinical docs that power close-gate + vitals/assessment/plan endpoints.
    Kept as-is for Phase-0 compatibility.
    """
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=32, choices=DocKind.choices, db_index=True)

    content = models.JSONField(default=dict)  # structured payload
    authored_at = models.DateTimeField(auto_now_add=True, db_index=True)
    authored_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authored_documents",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "clinical_docs_encounter_document"
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "encounter", "kind"]),
            models.Index(fields=["tenant_id", "facility_id", "authored_at"]),
        ]


class DocumentStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    FINAL = "FINAL", "Final"
    AMENDED = "AMENDED", "Amended"


class ClinicalDocument(models.Model):
    """
    Phase-1: Append-only, versioned clinical documents.
    Every logical change creates a NEW row (immutable rows).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant_id = models.UUIDField(db_index=True)
    facility_id = models.UUIDField(db_index=True)

    patient_id = models.UUIDField(db_index=True)
    encounter_id = models.UUIDField(db_index=True)

    template_code = models.CharField(max_length=100, db_index=True)
    version = models.PositiveIntegerField()

    idempotency_key = models.CharField(max_length=255, null=True, blank=True, db_index=True)

    status = models.CharField(max_length=16, choices=DocumentStatus.choices, db_index=True)

    # prior version this one supersedes (draft->final or final->amended)
    supersedes_document_id = models.UUIDField(null=True, blank=True, db_index=True)

    payload = models.JSONField(default=dict)

    # IMPORTANT:
    # Your system uses Django auth user_id as int (e.g., request.user.id),
    # so store it as integer, not UUID.
    created_by_user_id = models.BigIntegerField(db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "clinical_docs_clinical_document"

        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "facility_id", "encounter_id", "template_code", "idempotency_key"],
                condition=Q(status=DocumentStatus.DRAFT) & Q(idempotency_key__isnull=False),
                name="uniq_doc_idempo_draft",
            ),
            models.UniqueConstraint(
                fields=["tenant_id", "facility_id", "supersedes_document_id", "idempotency_key"],
                condition=Q(status=DocumentStatus.FINAL) & Q(idempotency_key__isnull=False),
                name="uniq_doc_idempo_finalize",
            ),
            models.UniqueConstraint(
                fields=["tenant_id", "facility_id", "supersedes_document_id", "idempotency_key"],
                condition=Q(status=DocumentStatus.AMENDED) & Q(idempotency_key__isnull=False),
                name="uniq_doc_idempo_amend",
            ),
    ]
        indexes = [
            models.Index(fields=["encounter_id", "template_code"]),
            models.Index(fields=["encounter_id", "created_at"]),
            models.Index(fields=["patient_id", "created_at"]),
            models.Index(fields=["tenant_id", "facility_id", "encounter_id", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.template_code} v{self.version} {self.status} ({self.encounter_id})"
