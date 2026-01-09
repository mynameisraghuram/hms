from __future__ import annotations

from django.contrib import admin
from django.contrib.admin import widgets
from django.db import models

from hm_core.rules.models import Rule


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "is_active",
        "tenant_id",
        "facility_id",
        "updated_at",
    )
    list_filter = ("is_active", "tenant_id", "facility_id")
    search_fields = ("code", "description")
    readonly_fields = ("created_at", "updated_at")

    # Make JSON config editable comfortably
    formfield_overrides = {
        models.JSONField: {"widget": widgets.AdminTextareaWidget(attrs={"rows": 18, "cols": 120})},
    }

    fieldsets = (
        ("Identity", {"fields": ("tenant_id", "facility_id", "code", "is_active")}),
        ("Details", {"fields": ("description",)}),
        ("Config", {"fields": ("config",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
