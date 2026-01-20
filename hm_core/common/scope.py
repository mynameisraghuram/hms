from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from rest_framework.exceptions import ValidationError

# Reuse canonical messages from iam.scope (single source of truth)
from hm_core.iam.scope import INVALID_SCOPE_MSG, MISSING_SCOPE_MSG


@dataclass(frozen=True)
class Scope:
    tenant_id: UUID
    facility_id: UUID


# Preferred header names (standard)
HDR_TENANT = "X-Tenant-Id"
HDR_FACILITY = "X-Facility-Id"

# Legacy variants (kept for compatibility)
HDR_TENANT_LEGACY = "X-Tenant-ID"
HDR_FACILITY_LEGACY = "X-Facility-ID"

HDR_TENANT_HM = "X-HM-Tenant-Id"
HDR_FACILITY_HM = "X-HM-Facility-Id"
HDR_TENANT_HM_LEGACY = "X-HM-Tenant-ID"
HDR_FACILITY_HM_LEGACY = "X-HM-Facility-ID"


def _parse_uuid(value: str) -> Optional[UUID]:
    try:
        return UUID(str(value))
    except Exception:
        return None


def _get_header(request, name: str) -> Optional[str]:
    """
    request.headers is case-insensitive; fallback to META for pytest/client.
    """
    try:
        v = request.headers.get(name)
        if v:
            return v
    except Exception:
        pass

    meta_key = "HTTP_" + name.upper().replace("-", "_")
    return request.META.get(meta_key)


def resolve_scope(request) -> Optional[Scope]:
    """
    Pure resolver:
    - Returns Scope if BOTH headers are present and valid
    - Returns None if NO scope headers are present at all
    - Returns sentinel Scope(None,None) behavior is NOT used here; we just return None or Scope
    """
    # Prefer middleware-attached values if present
    t = getattr(request, "tenant_id", None)
    f = getattr(request, "facility_id", None)
    if t and f:
        tu = _parse_uuid(str(t))
        fu = _parse_uuid(str(f))
        if tu and fu:
            return Scope(tenant_id=tu, facility_id=fu)

    tenant_raw = (
        _get_header(request, HDR_TENANT)
        or _get_header(request, HDR_TENANT_LEGACY)
        or _get_header(request, HDR_TENANT_HM)
        or _get_header(request, HDR_TENANT_HM_LEGACY)
    )
    facility_raw = (
        _get_header(request, HDR_FACILITY)
        or _get_header(request, HDR_FACILITY_LEGACY)
        or _get_header(request, HDR_FACILITY_HM)
        or _get_header(request, HDR_FACILITY_HM_LEGACY)
    )

    if not tenant_raw and not facility_raw:
        return None

    if not tenant_raw or not facility_raw:
        # Partial scope headers present
        raise ValidationError(MISSING_SCOPE_MSG)

    tenant_id = _parse_uuid(tenant_raw)
    facility_id = _parse_uuid(facility_raw)
    if not tenant_id or not facility_id:
        raise ValidationError(INVALID_SCOPE_MSG)

    return Scope(tenant_id=tenant_id, facility_id=facility_id)


def require_scope(request) -> Scope:
    """
    DRF-friendly scope requirement:
    - If missing -> raises ValidationError(MISSING_SCOPE_MSG)
    - If invalid -> raises ValidationError(INVALID_SCOPE_MSG)
    - If ok -> returns Scope and attaches request.tenant_id / request.facility_id / request.scope
    """
    scope = resolve_scope(request)
    if scope is None:
        raise ValidationError(MISSING_SCOPE_MSG)

    # Attach for downstream consistency
    request.tenant_id = scope.tenant_id
    request.facility_id = scope.facility_id
    request.scope = scope
    return scope
