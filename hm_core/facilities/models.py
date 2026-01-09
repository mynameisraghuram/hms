# backend/hm_core/facilities/models.py
from __future__ import annotations

import uuid

from django.db import models

from hm_core.tenants.models import Tenant


class FacilityType(models.TextChoices):
    HOSPITAL = "HOSPITAL", "Hospital"
    CLINIC = "CLINIC", "Clinic"
    LAB = "LAB", "Lab"
    PHARMACY = "PHARMACY", "Pharmacy"
    DIAGNOSTIC = "DIAGNOSTIC", "Diagnostic Center"
    OTHER = "OTHER", "Other"


class Facility(models.Model):
    """
    A branch/hospital/clinic under a Tenant.

    Notes (long-term):
    - Keep Facility as the "identity + basic metadata" record.
    - Avoid stuffing feature flags/settings here; prefer a separate FacilitySetting table later.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="facilities")

    # Core identity
    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=64)  # unique per tenant

    # Org structure
    facility_type = models.CharField(
        max_length=24,
        choices=FacilityType.choices,
        default=FacilityType.HOSPITAL,
        db_index=True,
    )
    parent_facility = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="child_facilities",
        null=True,
        blank=True,
    )

    # Locale / ops
    timezone = models.CharField(max_length=64, default="Asia/Kolkata")

    # Contact (optional)
    phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")

    # Address (optional)
    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=128, blank=True, default="")
    state = models.CharField(max_length=128, blank=True, default="")
    pincode = models.CharField(max_length=16, blank=True, default="")
    country = models.CharField(max_length=64, blank=True, default="India")

    # Regulatory / billing identifiers (optional, India-friendly)
    registration_number = models.CharField(max_length=64, blank=True, default="")
    gstin = models.CharField(max_length=32, blank=True, default="")

    # Lifecycle
    is_active = models.BooleanField(default=True, db_index=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivation_reason = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "facilities_facility"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uq_facility_tenant_code"),
            # Optional but useful: prevent duplicate names per tenant (comment out if you want duplicates)
            # models.UniqueConstraint(fields=["tenant", "name"], name="uq_facility_tenant_name"),
        ]
        indexes = [
            models.Index(fields=["tenant", "code"]),
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["tenant", "facility_type"]),
            models.Index(fields=["tenant", "parent_facility"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"
