# backend/hm_core/tasks/admin.py
from __future__ import annotations

from django.contrib import admin

from hm_core.tasks.models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant_id",
        "facility_id",
        "encounter_id",
        "code",
        "title",
        "status",
        "assigned_to",
        "due_at",
        "completed_at",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "code")
    search_fields = ("id", "encounter_id", "code", "title")
    ordering = ("-created_at",)

    readonly_fields = ("created_at", "updated_at")

    # helps performance on large tables
    list_select_related = ("encounter", "assigned_to")

    fieldsets = (
        ("Scope", {"fields": ("tenant_id", "facility_id")}),
        ("Task", {"fields": ("encounter", "code", "title", "status")}),
        ("Assignment", {"fields": ("assigned_to",)}),
        ("Timing", {"fields": ("due_at", "completed_at")}),
        ("Audit", {"fields": ("created_at", "updated_at")}),
    )
