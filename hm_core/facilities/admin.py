# backend/hm_core/facilities/admin.py
from __future__ import annotations

from django.contrib import admin

from hm_core.facilities.models import Facility


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "tenant",
        "facility_type",
        "is_active",
        "timezone",
        "city",
        "state",
        "updated_at",
    )
    list_filter = ("is_active", "facility_type", "timezone", "state", "country", "tenant")
    search_fields = ("name", "code", "tenant__code", "tenant__name", "city", "state", "pincode")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("tenant", "name")
