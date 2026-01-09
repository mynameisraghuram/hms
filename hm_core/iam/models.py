# backend/hm_core/iam/models.py
import uuid
from django.conf import settings
from django.db import models
from hm_core.tenants.models import Tenant
from hm_core.facilities.models import Facility


class Permission(models.Model):
    """
    Atomic capability: e.g. "encounters.close", "patients.create"
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    code = models.CharField(max_length=128, unique=True)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "iam_permission"
        indexes = [models.Index(fields=["code"])]

    def __str__(self) -> str:
        return self.code


class Role(models.Model):
    """
    Role is tenant-scoped (different tenants can define their own roles).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="roles")

    name = models.CharField(max_length=128)
    code = models.SlugField(max_length=64)  # unique per tenant

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "iam_role"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uq_role_tenant_code"),
        ]
        indexes = [
            models.Index(fields=["tenant", "code"]),
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.code}"


class RolePermission(models.Model):
    """
    Many-to-many Role <-> Permission.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(Permission, on_delete=models.PROTECT, related_name="permission_roles")

    class Meta:
        db_table = "iam_role_permission"
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="uq_role_permission"),
        ]


class UserProfile(models.Model):
    """
    HM Software user profile anchored to Django's AUTH_USER_MODEL.
    Tenant-scoped identity wrapper.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hm_profile")
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="user_profiles")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "iam_user_profile"
        indexes = [
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} ({self.tenant.code})"


class FacilityMembership(models.Model):
    """
    Assigns a user to a facility with a role.
    This is the RBAC enforcement point for facility-level access.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, related_name="facility_memberships")
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="memberships")

    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="memberships")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="memberships")

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "iam_facility_membership"
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "user_profile"],
                name="uq_facility_user_profile_membership",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "facility"]),
            models.Index(fields=["tenant", "is_active"]),
        ]
