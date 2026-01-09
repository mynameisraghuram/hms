# backend/hm_core/common/middleware.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin


@dataclass(frozen=True)
class RequestScope:
    tenant_id: UUID
    facility_id: UUID


def _parse_uuid(value: str) -> Optional[UUID]:
    try:
        return UUID(str(value))
    except Exception:
        return None


class TenantFacilityScopeMiddleware(MiddlewareMixin):
    """
    Enforces tenant/facility scope for API requests.

    Supported header variants (META keys):
      Preferred (new):
        - X-Tenant-Id     -> HTTP_X_TENANT_ID
        - X-Facility-Id   -> HTTP_X_FACILITY_ID
      Legacy/test (current repo tests):
        - X-HM-Tenant-Id  -> HTTP_X_HM_TENANT_ID
        - X-HM-Facility-Id-> HTTP_X_HM_FACILITY_ID

    Behavior:
      - Enforced for both /api/v1/* and /api/* (alias).
      - For most endpoints: BOTH headers are required (400 if missing).
      - For /me/: headers are OPTIONAL, but if provided they must be valid and user must be a member.
      - For auth endpoints (login/refresh/logout): scope is ignored (never required).
      - If invalid UUIDs -> 400
      - If user not a member of facility -> 403
      - On success -> attaches request.scope, request.tenant_id, request.facility_id
    """

    TENANT_META_KEYS = ("HTTP_X_TENANT_ID", "HTTP_X_HM_TENANT_ID")
    FACILITY_META_KEYS = ("HTTP_X_FACILITY_ID", "HTTP_X_HM_FACILITY_ID")

    ENFORCED_PREFIXES = ("/api/v1/", "/api/")

    AUTH_PATH_SUFFIXES = (
        "/auth/login/",
        "/auth/refresh/",
        "/auth/logout/",
    )

    ALLOW_NO_SCOPE_SUFFIXES = (
        "/me/",
    )

    MISSING_SCOPE_MSG = "Missing scope headers. Provide X-Tenant-Id and X-Facility-Id."
    INVALID_SCOPE_MSG = "Invalid scope headers. Provide valid UUIDs for X-Tenant-Id and X-Facility-Id."

    def _is_api_path(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.ENFORCED_PREFIXES)

    def _endswith_any(self, path: str, suffixes: tuple[str, ...]) -> bool:
        return any(path.endswith(s) for s in suffixes)

    def _get_meta_first(self, request, keys: tuple[str, ...]) -> Optional[str]:
        for k in keys:
            v = request.META.get(k)
            if v:
                return v
        return None

    def process_request(self, request):
        request.scope = None
        request.tenant_id = None
        request.facility_id = None

        path = getattr(request, "path", "") or ""
        if not self._is_api_path(path):
            return None

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None

        if self._endswith_any(path, self.AUTH_PATH_SUFFIXES):
            return None

        tenant_raw = self._get_meta_first(request, self.TENANT_META_KEYS)
        facility_raw = self._get_meta_first(request, self.FACILITY_META_KEYS)

        # No scope headers at all
        if not tenant_raw and not facility_raw:
            if self._endswith_any(path, self.ALLOW_NO_SCOPE_SUFFIXES):
                return None
            return JsonResponse({"detail": self.MISSING_SCOPE_MSG}, status=400)

        # Only one present
        if not tenant_raw or not facility_raw:
            return JsonResponse({"detail": self.MISSING_SCOPE_MSG}, status=400)

        tenant_id = _parse_uuid(tenant_raw)
        facility_id = _parse_uuid(facility_raw)
        if not tenant_id or not facility_id:
            return JsonResponse({"detail": self.INVALID_SCOPE_MSG}, status=400)

        from hm_core.iam.services.membership import is_user_member_of_facility

        if not is_user_member_of_facility(user_id=user.id, tenant_id=tenant_id, facility_id=facility_id):
            return JsonResponse({"detail": "You do not have access to the selected facility."}, status=403)

        request.scope = RequestScope(tenant_id=tenant_id, facility_id=facility_id)
        request.tenant_id = tenant_id
        request.facility_id = facility_id
        return None
