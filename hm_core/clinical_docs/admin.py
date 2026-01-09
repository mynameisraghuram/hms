# backend/hm_core/clinical_docs/admin.py
from __future__ import annotations

from django.contrib import admin

from hm_core.clinical_docs.models import ClinicalDocument, EncounterDocument


@admin.register(EncounterDocument)
class EncounterDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant_id",
        "facility_id",
        "encounter",
        "kind",
        "authored_at",
        "authored_by",
    )
    list_filter = ("kind",)
    search_fields = ("id", "encounter__id", "tenant_id", "facility_id")
    readonly_fields = ("id", "authored_at", "created_at", "updated_at")
    ordering = ("-authored_at",)


@admin.register(ClinicalDocument)
class ClinicalDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant_id",
        "facility_id",
        "patient_id",
        "encounter_id",
        "template_code",
        "version",
        "status",
        "supersedes_document_id",
        "created_by_user_id",
        "created_at",
    )
    list_filter = ("status", "template_code")
    search_fields = ("id", "patient_id", "encounter_id", "template_code", "tenant_id", "facility_id")
    readonly_fields = ("id", "version", "created_at")
    ordering = ("-created_at",)
