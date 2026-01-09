# backend/hm_core/clinical_docs/api/serializers.py
from __future__ import annotations

from rest_framework import serializers

from hm_core.clinical_docs.models import ClinicalDocument, EncounterDocument


# ----------------------------
# Phase-0 serializer (EncounterDocument)
# ----------------------------
class EncounterDocumentSerializer(serializers.ModelSerializer):
    encounter_id = serializers.UUIDField(source="encounter.id", read_only=True)

    class Meta:
        model = EncounterDocument
        fields = [
            "id",
            "tenant_id",
            "facility_id",
            "encounter_id",
            "kind",
            "content",
            "authored_at",
            "authored_by",
        ]


# ----------------------------
# Phase-1 serializer (ClinicalDocument)
# ----------------------------
class ClinicalDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalDocument
        fields = [
            "id",
            "tenant_id",
            "facility_id",
            "patient_id",
            "encounter_id",
            "template_code",
            "version",
            "status",
            "supersedes_document_id",
            "payload",
            "idempotency_key",
            "created_by_user_id",
            "created_at",
        ]


class CreateDraftSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    template_code = serializers.CharField(max_length=100)
    payload = serializers.JSONField(required=False, default=dict)
    idempotency_key = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class AmendSerializer(serializers.Serializer):
    payload_patch = serializers.JSONField()
    idempotency_key = serializers.CharField(required=False, allow_blank=True, allow_null=True)
