# backend/hm_core/lab/admin.py
from __future__ import annotations

from django.contrib import admin

from hm_core.lab.models import LabSample, LabResult


@admin.register(LabSample)
class LabSampleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant_id",
        "facility_id",
        "order_item",
        "barcode",
        "received_at",
        "received_by",
        "created_at",
    )
    list_filter = ("tenant_id", "facility_id", "received_at")
    search_fields = ("id", "barcode", "order_item__id")
    autocomplete_fields = ("order_item", "received_by")
    ordering = ("-created_at",)


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant_id",
        "facility_id",
        "order_item",
        "encounter",
        "version",
        "is_critical",
        "verified_at",
        "released_at",
        "created_at",
    )
    list_filter = ("tenant_id", "facility_id", "is_critical", "verified_at", "released_at")
    search_fields = ("id", "order_item__id", "encounter__id", "order_item__service_code")
    autocomplete_fields = ("order_item", "encounter", "verified_by", "released_by")
    ordering = ("-created_at",)
