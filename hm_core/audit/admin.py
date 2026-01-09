# backend/hm_core/audit/admin.py
from django.contrib import admin

from hm_core.audit.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_code",
        "entity_type",
        "entity_id",
        "tenant_id",
        "facility_id",
        "actor_user",
        "occurred_at",
    )
    list_filter = ("tenant_id", "facility_id", "event_code", "entity_type")
    search_fields = ("event_code", "entity_type", "entity_id")
    readonly_fields = ("occurred_at",)
    ordering = ("-occurred_at",)
