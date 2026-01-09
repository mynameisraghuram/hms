# backend/hm_core/iam/scope.py
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from rest_framework.exceptions import PermissionDenied, ValidationError

from hm_core.iam.services.membership import is_user_member_of_facility


@dataclass(frozen=True)
class Scope:
    tenant_id: UUID
    facility_id: UUID


# Preferred header names (what we standardize on)
HDR_TENANT = "X-Tenant-Id"
HDR_FACILITY = "X-Facility-Id"

# Legacy variants (kept for compatibility)
HDR_TENANT_LEGACY = "X-Tenant-ID"
HDR_FACILITY_LEGACY = "X-Facility-ID"

MISSING_SCOPE_MSG = "Missing scope headers. Provide X-Tenant-Id and X-Facility-Id."
INVALID_SCOPE_MSG = "Invalid scope headers. Provide valid UUIDs for X-Tenant-Id and X-Facility-Id."


def _parse_uuid(value: str, header_name: str) -> UUID:
    try:
        return UUID(str(value))
    except Exception:
        # DRF-friendly error shape
        raise ValidationError({header_name: "Invalid UUID"})


def _get_header(request, name: str) -> str | None:
    # request.headers is case-insensitive; returns None if missing
    try:
        return request.headers.get(name)
    except Exception:
        return None


def resolve_scope_from_headers(request) -> Scope | None:
    """
    Reads scope headers. Returns Scope if both are present.
    - If neither is present: returns None.
    - If only one is present: raises 400 ValidationError with MISSING_SCOPE_MSG.
    """
    tenant_raw = _get_header(request, HDR_TENANT) or _get_header(request, HDR_TENANT_LEGACY)
    facility_raw = _get_header(request, HDR_FACILITY) or _get_header(request, HDR_FACILITY_LEGACY)

    if not tenant_raw and not facility_raw:
        return None

    if not tenant_raw or not facility_raw:
        raise ValidationError(MISSING_SCOPE_MSG)

    tenant_id = _parse_uuid(tenant_raw, HDR_TENANT)
    facility_id = _parse_uuid(facility_raw, HDR_FACILITY)
    return Scope(tenant_id=tenant_id, facility_id=facility_id)


def require_scope_from_headers(request) -> Scope:
    scope = resolve_scope_from_headers(request)
    if scope is None:
        raise ValidationError(MISSING_SCOPE_MSG)
    return scope


def assert_user_membership(user, scope: Scope) -> None:
    """
    Ensures user is a member of (tenant_id, facility_id).
    Uses membership service (works with user_profile-based membership models).
    Raises 403 if not.
    """
    if not user or not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication required to set scope.")

    ok = is_user_member_of_facility(
        user_id=user.id,
        tenant_id=scope.tenant_id,
        facility_id=scope.facility_id,
    )
    if not ok:
        raise PermissionDenied("You do not have access to the selected facility.")


def apply_scope_from_headers(request, user=None) -> Scope | None:
    """
    Public API used by auth layer (CookieOrHeaderJWTAuthentication).

    If scope headers are present:
      - validates they are UUIDs
      - verifies user membership
      - sets request.tenant_id and request.facility_id
      - sets request.scope
      - returns Scope

    If no scope headers: returns None and does nothing.
    """
    scope = resolve_scope_from_headers(request)
    if scope is None:
        return None

    u = user or getattr(request, "user", None)
    assert_user_membership(u, scope)

    request.tenant_id = scope.tenant_id
    request.facility_id = scope.facility_id
    request.scope = scope
    return scope
