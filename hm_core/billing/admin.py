# backend/hm_core/billing/admin.py
from __future__ import annotations

from django.contrib import admin

from hm_core.billing.models import BillableEvent


@admin.register(BillableEvent)
class BillableEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant_id",
        "facility_id",
        "encounter",
        "event_type",
        "chargeable_code",
        "quantity",
        "source_order_item",
        "created_at",
    )
    list_filter = ("tenant_id", "facility_id", "event_type", "created_at")
    search_fields = ("id", "chargeable_code", "encounter__id", "source_order_item__id")
    autocomplete_fields = ("encounter", "source_order_item")
    ordering = ("-created_at",)
