# backend/hm_core/common/scope.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from rest_framework import status
from rest_framework.response import Response

# Reuse the canonical messages from iam.scope (single source of truth)
from hm_core.iam.scope import MISSING_SCOPE_MSG, INVALID_SCOPE_MSG


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
    Returns Scope if BOTH headers are present and valid.
    Returns None if NO scope headers are present at all.
    Raises nothing (pure resolver).
    """
    # Prefer middleware-attached values if present
    t = getattr(request, "tenant_id", None)
    f = getattr(request, "facility_id", None)
    if t and f:
        tu = _parse_uuid(str(t))
        fu = _parse_uuid(str(f))
        if tu and fu:
            return Scope(tenant_id=tu, facility_id=fu)

    # Otherwise read headers (preferred + legacy)
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
        # Partial headers present -> treat as invalid usage (caller decides response)
        return Scope(tenant_id=None, facility_id=None)  # type: ignore

    tenant_id = _parse_uuid(tenant_raw)
    facility_id = _parse_uuid(facility_raw)
    if not tenant_id or not facility_id:
        return Scope(tenant_id=None, facility_id=None)  # type: ignore

    return Scope(tenant_id=tenant_id, facility_id=facility_id)


def require_scope_or_400(request) -> tuple[UUID | None, UUID | None, Response | None]:
    """
    Returns (tenant_id, facility_id, error_response).

    - If missing -> 400 with MISSING_SCOPE_MSG
    - If invalid -> 400 with INVALID_SCOPE_MSG
    - If ok -> (tenant_id, facility_id, None)

    Does NOT check membership — membership is enforced by middleware/auth/permission layer.
    (So this stays reusable and doesn’t create circular dependencies.)
    """
    scope = resolve_scope(request)

    if scope is None:
        return None, None, Response({"detail": MISSING_SCOPE_MSG}, status=status.HTTP_400_BAD_REQUEST)

    # We used a sentinel invalid Scope(tenant_id=None,...)
    if getattr(scope, "tenant_id", None) is None or getattr(scope, "facility_id", None) is None:
        # Distinguish missing-vs-invalid:
        # If one header missing, resolve_scope returns the sentinel too.
        tenant_present = any(
            _get_header(request, h)
            for h in (HDR_TENANT, HDR_TENANT_LEGACY, HDR_TENANT_HM, HDR_TENANT_HM_LEGACY)
        )
        facility_present = any(
            _get_header(request, h)
            for h in (HDR_FACILITY, HDR_FACILITY_LEGACY, HDR_FACILITY_HM, HDR_FACILITY_HM_LEGACY)
        )
        msg = INVALID_SCOPE_MSG if (tenant_present and facility_present) else MISSING_SCOPE_MSG
        return None, None, Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

    # Attach for downstream consistency (optional but helpful)
    request.tenant_id = scope.tenant_id
    request.facility_id = scope.facility_id
    request.scope = scope

    return scope.tenant_id, scope.facility_id, None
