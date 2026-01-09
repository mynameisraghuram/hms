# backend/hm_core/tenants/admin.py
from django.contrib import admin

from hm_core.tenants.models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "code")
    ordering = ("-created_at",)
    readonly_fields = ("id", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("id", "name", "code", "status")}),
        ("Metadata", {"fields": ("metadata",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
