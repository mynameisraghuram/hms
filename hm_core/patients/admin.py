# backend/hm_core/patients/admin.py
from django.contrib import admin

from hm_core.patients.models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "mrn",
        "phone",
        "email",
        "tenant_id",
        "facility_id",
        "created_at",
    )
    list_filter = ("tenant_id", "facility_id")
    search_fields = ("full_name", "mrn", "phone", "email")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
