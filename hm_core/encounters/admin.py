# backend/hm_core/encounters/admin.py
from __future__ import annotations

from django.contrib import admin

from hm_core.encounters.models import Encounter, EncounterEvent


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant_id",
        "facility_id",
        "patient",
        "status",
        "scheduled_at",
        "checked_in_at",
        "consult_started_at",
        "closed_at",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("id", "patient__id", "patient__mrn", "patient__full_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(EncounterEvent)
class EncounterEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant_id",
        "facility_id",
        "encounter_id",
        "code",
        "event_key",
        "timestamp",
        "created_at",
    )
    list_filter = ("code",)
    search_fields = ("encounter_id", "event_key", "code")
    readonly_fields = (
        "id",
        "tenant_id",
        "facility_id",
        "encounter_id",
        "type",
        "event_key",
        "code",
        "title",
        "timestamp",
        "meta",
        "created_at",
    )

    def has_add_permission(self, request):
        # prevent manual mutation; events should be written by code
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
