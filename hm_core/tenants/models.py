# backend/hm_core/tenants/models.py
import uuid
from django.db import models


class TenantStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    SUSPENDED = "SUSPENDED", "Suspended"
    DELETED = "DELETED", "Deleted"


class Tenant(models.Model):
    """
    Top-level organization.
    Root of all scoping in the system.
    NOT a ScopedModel (it *is* the tenant).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)
    code = models.SlugField(max_length=64, unique=True)  # stable identifier (subdomain-friendly)

    status = models.CharField(
        max_length=16,
        choices=TenantStatus.choices,
        default=TenantStatus.ACTIVE,
        db_index=True,
    )

    # flexible, avoids schema churn (feature flags, onboarding, internal notes, etc.)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenants_tenant"
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"
