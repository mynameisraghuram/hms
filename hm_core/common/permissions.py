# backend/hm_core/common/permissions.py

from __future__ import annotations

from typing import Set
from uuid import UUID

from rest_framework.permissions import BasePermission, SAFE_METHODS

# Group/role names (Django auth Group names recommended)
ROLE_ADMIN = "ADMIN"
ROLE_DOCTOR = "DOCTOR"
ROLE_NURSE = "NURSE"
ROLE_RECEPTION = "RECEPTION"
ROLE_LAB = "LAB"
ROLE_BILLING = "BILLING"
ROLE_READONLY = "READONLY"


def _user_roles(user) -> Set[str]:
    """
    Resolve roles from:
    1) Django groups: user.groups (recommended)
    2) Optional user.role attribute (if your project has it)

    Returns set of role strings.

    Default behavior:
    - If authenticated user has no roles/groups, treat them as READONLY.
    """
    roles: Set[str] = set()

    if not user or not getattr(user, "is_authenticated", False):
        return roles

    # Superuser treated as admin
    if getattr(user, "is_superuser", False):
        roles.add(ROLE_ADMIN)
        return roles

    # Django Groups
    if hasattr(user, "groups"):
        roles.update(user.groups.values_list("name", flat=True))

    # Optional user.role or user.roles
    if hasattr(user, "role") and user.role:
        roles.add(str(user.role))

    if hasattr(user, "roles") and user.roles:
        try:
            roles.update(set(user.roles))
        except TypeError:
            roles.add(str(user.roles))

    # ✅ Ensure authenticated users without explicit roles can still read
    if not roles:
        roles.add(ROLE_READONLY)

    return roles


# -----------------------------
# Scope helpers (Tenant/Facility)
# -----------------------------

def _get_header(request, name: str) -> str | None:
    """
    Prefer request.headers (case-insensitive), fallback to META (pytest uses HTTP_*).
    """
    v = request.headers.get(name)
    if v:
        return v
    meta_key = "HTTP_" + name.upper().replace("-", "_")
    return request.META.get(meta_key)


def _first_header(request, candidates: list[str]) -> str | None:
    for c in candidates:
        v = _get_header(request, c)
        if v:
            return v
    return None


def ensure_scope_on_request(request) -> bool:
    """
    Ensure request.tenant_id and request.facility_id exist.

    IMPORTANT:
    - Permissions must not raise ValidationError (it becomes 400).
    - Return False when missing/invalid -> DRF returns 403.

    Supports BOTH header families:
    - HM headers: X_HM_TENANT_ID / X_HM_FACILITY_ID (and hyphen versions)
    - Generic headers: X_TENANT_ID / X_FACILITY_ID (and hyphen versions)
    """
    tenant_id = getattr(request, "tenant_id", None)
    facility_id = getattr(request, "facility_id", None)

    if tenant_id and facility_id:
        return True

    raw_tenant = _first_header(
        request,
        [
            # ✅ your project’s headers
            "X_HM_TENANT_ID",
            "X-HM-TENANT-ID",
            "X_HM_TENANT_ID".lower(),
            # ✅ generic/older variants
            "X_TENANT_ID",
            "X-TENANT-ID",
            "X_TENANT_ID".lower(),
        ],
    )

    raw_facility = _first_header(
        request,
        [
            # ✅ your project’s headers
            "X_HM_FACILITY_ID",
            "X-HM-FACILITY-ID",
            "X_HM_FACILITY_ID".lower(),
            # ✅ generic/older variants
            "X_FACILITY_ID",
            "X-FACILITY-ID",
            "X_FACILITY_ID".lower(),
        ],
    )

    if not raw_tenant or not raw_facility:
        return False

    try:
        tenant_uuid = UUID(str(raw_tenant))
        facility_uuid = UUID(str(raw_facility))
    except Exception:
        return False

    setattr(request, "tenant_id", tenant_uuid)
    setattr(request, "facility_id", facility_uuid)
    return True


class BaseRolePermission(BasePermission):
    """
    Base permission class for role-based access control.

    Key behavior:
    - Requires authentication (your global IsAuthenticated already does this).
    - ADMIN bypass.
    - Uses allowed_roles_per_action for strict RBAC.
    - ✅ If action is unknown and request is SAFE, fall back to list/retrieve
      instead of denying (prevents random 403s for @action endpoints when
      method name doesn't match the permission map).
    """
    message = "You do not have permission to perform this action."

    # Override in subclasses: dict of action -> set of allowed roles
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "create": {ROLE_ADMIN},
        "update": {ROLE_ADMIN},
        "partial_update": {ROLE_ADMIN},
        "destroy": {ROLE_ADMIN},
    }

    def _infer_action(self, request, view) -> str | None:
        action = getattr(view, "action", None)
        if action:
            return action

        # fallback inference when action isn't set
        kwargs = getattr(view, "kwargs", {}) or {}
        is_detail = "pk" in kwargs or "id" in kwargs

        method = request.method.upper()
        if method in ("GET", "HEAD", "OPTIONS"):
            return "retrieve" if is_detail else "list"
        if method == "POST":
            return "create"
        if method == "PUT":
            return "update"
        if method == "PATCH":
            return "partial_update"
        if method == "DELETE":
            return "destroy"
        return None

    def has_permission(self, request, view) -> bool:
        # ✅ enforce scope at permission layer (prevents 400s)
        if not ensure_scope_on_request(request):
            return False

        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False

        roles = _user_roles(user)

        # ADMIN can do everything
        if ROLE_ADMIN in roles:
            return True

        action = self._infer_action(request, view)
        allowed = self.allowed_roles_per_action.get(action)

        # ✅ Robust fallback for SAFE methods:
        if allowed is None and request.method in SAFE_METHODS:
            kwargs = getattr(view, "kwargs", {}) or {}
            is_detail = "pk" in kwargs or "id" in kwargs
            read_action = "retrieve" if is_detail else "list"
            allowed = self.allowed_roles_per_action.get(read_action)

        if allowed is not None:
            return bool(roles & allowed)

        # Unknown action => deny by default (safer)
        return False

    def has_object_permission(self, request, view, obj) -> bool:
        return self.has_permission(request, view)


# Specific permission classes for each module

class PatientPermission(BaseRolePermission):
    """Permissions for Patient management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "create": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION},
        "update": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "partial_update": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "destroy": {ROLE_ADMIN},
    }


class EncounterPermission(BaseRolePermission):
    """Permissions for Encounter management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "create": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION},
        "update": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "partial_update": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "destroy": {ROLE_ADMIN},
        # Custom actions
        "checkin": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION},
        "start_consult": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "close": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "close_gate": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION},
        "vitals": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "assessment": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "plan": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "timeline": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
    }


class PharmacyPermission(BaseRolePermission):
    """Permissions for Pharmacy management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "create": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "update": {ROLE_ADMIN, ROLE_LAB, ROLE_BILLING},
        "partial_update": {ROLE_ADMIN, ROLE_LAB, ROLE_BILLING},
        "destroy": {ROLE_ADMIN},
        "finalize": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "dispense": {ROLE_ADMIN, ROLE_LAB},
    }


class AppointmentPermission(BaseRolePermission):
    """Permissions for Appointment management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_READONLY},
        "create": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION},
        "update": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION},
        "partial_update": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION},
        "destroy": {ROLE_ADMIN, ROLE_RECEPTION},
        "available_slots": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION},
        "confirm": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION},
        "cancel": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION},
        "checkin": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION},
    }


class IPDPermission(BaseRolePermission):
    """Permissions for IPD (Inpatient Department) management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_BILLING, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_BILLING, ROLE_READONLY},
        "create": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION},
        "update": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "partial_update": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "destroy": {ROLE_ADMIN},
        "admit": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION},
        "discharge": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "transfer": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
    }


class RadiologyPermission(BaseRolePermission):
    """Permissions for Radiology management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_READONLY},
        "create": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "update": {ROLE_ADMIN, ROLE_LAB},
        "partial_update": {ROLE_ADMIN, ROLE_LAB},
        "destroy": {ROLE_ADMIN},
        "report": {ROLE_ADMIN, ROLE_LAB},
        "verify": {ROLE_ADMIN, ROLE_DOCTOR},
    }


class InventoryPermission(BaseRolePermission):
    """Permissions for Inventory management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "create": {ROLE_ADMIN, ROLE_BILLING},
        "update": {ROLE_ADMIN, ROLE_BILLING},
        "partial_update": {ROLE_ADMIN, ROLE_BILLING},
        "destroy": {ROLE_ADMIN},
        "adjust_stock": {ROLE_ADMIN, ROLE_BILLING},
        "low_stock_alerts": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_BILLING},
        "expiry_alerts": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_BILLING},
    }


class NotificationPermission(BaseRolePermission):
    """Permissions for Notification management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "create": {ROLE_ADMIN},
        "update": {ROLE_ADMIN},
        "partial_update": {ROLE_ADMIN},
        "destroy": {ROLE_ADMIN},
        "send_bulk": {ROLE_ADMIN},
        "mark_read": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_LAB, ROLE_BILLING},
        "preferences": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_LAB, ROLE_BILLING},
    }


class FileUploadPermission(BaseRolePermission):
    """Permissions for File Upload management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "create": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB},
        "update": {ROLE_ADMIN},
        "partial_update": {ROLE_ADMIN},
        "destroy": {ROLE_ADMIN},
    }


class SearchPermission(BaseRolePermission):
    """Permissions for Search functionality"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "create": set(),
        "update": set(),
        "partial_update": set(),
        "destroy": set(),
    }


class OrderPermission(BaseRolePermission):
    """Permissions for Order management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_BILLING, ROLE_READONLY},
        "create": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "update": {ROLE_ADMIN, ROLE_LAB, ROLE_BILLING},
        "partial_update": {ROLE_ADMIN, ROLE_LAB, ROLE_BILLING},
        "destroy": {ROLE_ADMIN},
    }


class LabPermission(BaseRolePermission):
    """Permissions for Lab management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_LAB, ROLE_READONLY},
        "create": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "update": {ROLE_ADMIN, ROLE_LAB},
        "partial_update": {ROLE_ADMIN, ROLE_LAB},
        "destroy": {ROLE_ADMIN},
        "receive_sample": {ROLE_ADMIN, ROLE_LAB},
        "enter_results": {ROLE_ADMIN, ROLE_LAB},
        "verify_release": {ROLE_ADMIN, ROLE_LAB},
    }


class AlertPermission(BaseRolePermission):
    """Permissions for Alert management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_READONLY},
        "create": {ROLE_ADMIN},
        "update": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "partial_update": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "destroy": {ROLE_ADMIN},
        "acknowledge": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
    }


class BillingPermission(BaseRolePermission):
    """Permissions for Billing management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_BILLING, ROLE_READONLY},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE, ROLE_RECEPTION, ROLE_BILLING, ROLE_READONLY},
        "create": {ROLE_ADMIN, ROLE_BILLING},
        "update": {ROLE_ADMIN, ROLE_BILLING},
        "partial_update": {ROLE_ADMIN, ROLE_BILLING},
        "destroy": {ROLE_ADMIN},
    }


class AuditPermission(BaseRolePermission):
    """Permissions for Audit log access"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN},
        "retrieve": {ROLE_ADMIN},
        "create": set(),
        "update": set(),
        "partial_update": set(),
        "destroy": set(),
    }


class RulePermission(BaseRolePermission):
    """Permissions for Rule engine management"""
    allowed_roles_per_action = {
        "list": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "retrieve": {ROLE_ADMIN, ROLE_DOCTOR, ROLE_NURSE},
        "create": {ROLE_ADMIN},
        "update": {ROLE_ADMIN},
        "partial_update": {ROLE_ADMIN},
        "destroy": {ROLE_ADMIN},
    }
