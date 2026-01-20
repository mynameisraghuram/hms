from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from hm_core.common.api.exceptions import build_error_envelope
from hm_core.iam.scope import INVALID_SCOPE_MSG, MISSING_SCOPE_MSG


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

    Behavior:
      - Enforced for both /api/v1/* and /api/* (alias).
      - For most endpoints: BOTH headers are required (400 if missing).
      - For /me/ and /session/bootstrap/: headers are OPTIONAL, but if provided they must be valid
        and user must be a member.
      - For auth endpoints (login/refresh/logout): scope is ignored (never required).
      - Docs/schema/admin endpoints: public.
      - If invalid UUIDs -> 400
      - If user not a member -> 403
      - On success -> attaches request.scope, request.tenant_id, request.facility_id
    """

    TENANT_META_KEYS = ("HTTP_X_TENANT_ID", "HTTP_X_HM_TENANT_ID")
    FACILITY_META_KEYS = ("HTTP_X_FACILITY_ID", "HTTP_X_HM_FACILITY_ID")

    ENFORCED_PREFIXES = ("/api/v1/", "/api/")

    PUBLIC_PATH_PREFIXES = (
        "/admin/",
        "/api/docs/",
        "/api/schema/",
    )

    AUTH_PATH_SUFFIXES = (
        "/auth/login/",
        "/auth/refresh/",
        "/auth/logout/",
    )

    ALLOW_NO_SCOPE_EXACT_PATHS = (
        "/api/v1/",
        "/api/",
    )

    ALLOW_NO_SCOPE_SUFFIXES = (
        "/me/",
        "/session/bootstrap/",
    )

    def _is_api_path(self, path: str) -> bool:
        return any(path.startswith(p) for p in self.ENFORCED_PREFIXES)

    def _starts_with_any(self, path: str, prefixes: tuple[str, ...]) -> bool:
        return any(path.startswith(p) for p in prefixes)

    def _endswith_any(self, path: str, suffixes: tuple[str, ...]) -> bool:
        return any(path.endswith(s) for s in suffixes)

    def _get_meta_first(self, request, keys: tuple[str, ...]) -> Optional[str]:
        for k in keys:
            v = request.META.get(k)
            if v:
                return v
        return None

    def _json_error(self, request, *, status_code: int, code: str, message: str, details=None) -> JsonResponse:
        return JsonResponse(
            build_error_envelope(
                request=request,
                code=code,
                message=message,
                details=details,
            ),
            status=status_code,
        )

    def process_request(self, request):
        request.scope = None
        request.tenant_id = None
        request.facility_id = None

        path = getattr(request, "path", "") or ""

        # Always allow docs/schema/admin without scope/auth.
        if self._starts_with_any(path, self.PUBLIC_PATH_PREFIXES):
            return None

        # If it's not under /api/ or /api/v1/, ignore.
        if not self._is_api_path(path):
            return None

        # Allow visiting API roots without forcing scope
        if path in self.ALLOW_NO_SCOPE_EXACT_PATHS:
            return None

        # Auth endpoints never require scope
        if self._endswith_any(path, self.AUTH_PATH_SUFFIXES):
            return None

        # If user isn't authenticated, don't enforce scope here.
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None

        tenant_raw = self._get_meta_first(request, self.TENANT_META_KEYS)
        facility_raw = self._get_meta_first(request, self.FACILITY_META_KEYS)

        # No scope headers at all
        if not tenant_raw and not facility_raw:
            if self._endswith_any(path, self.ALLOW_NO_SCOPE_SUFFIXES):
                return None
            return self._json_error(
                request,
                status_code=400,
                code="validation_error",
                message=MISSING_SCOPE_MSG,
                details=None,
            )

        # Only one present
        if not tenant_raw or not facility_raw:
            return self._json_error(
                request,
                status_code=400,
                code="validation_error",
                message=MISSING_SCOPE_MSG,
                details=None,
            )

        tenant_id = _parse_uuid(tenant_raw)
        facility_id = _parse_uuid(facility_raw)
        if not tenant_id or not facility_id:
            return self._json_error(
                request,
                status_code=400,
                code="validation_error",
                message=INVALID_SCOPE_MSG,
                details=None,
            )

        from hm_core.iam.services.membership import is_user_member_of_facility

        if not is_user_member_of_facility(user_id=user.id, tenant_id=tenant_id, facility_id=facility_id):
            return self._json_error(
                request,
                status_code=403,
                code="permission_denied",
                message="You do not have access to the selected facility.",
                details=None,
            )

        request.scope = RequestScope(tenant_id=tenant_id, facility_id=facility_id)
        request.tenant_id = tenant_id
        request.facility_id = facility_id
        return None
