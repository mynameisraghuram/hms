#base/backend/hm_core/common/api/exceptions.py

from __future__ import annotations

import uuid
from typing import Any

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, NotAuthenticated, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def ensure_request_id(request) -> str:
    """
    Ensures request has a stable request_id attribute and returns it.
    Safe to call from middleware and DRF exception handler.
    """
    rid = getattr(request, "request_id", None) if request is not None else None
    if not rid:
        rid = uuid.uuid4().hex
        if request is not None:
            setattr(request, "request_id", rid)
    return rid


def build_error_envelope(*, request=None, code: str, message: str, details: Any = None) -> dict[str, Any]:
    """
    Canonical error envelope for HM Software.
    This is intentionally reusable from Django middleware (JsonResponse) and DRF (Response).
    """
    rid = ensure_request_id(request)
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": rid,
        }
    }


class ConflictError(APIException):
    """
    409 Conflict that still flows through the global exception handler.
    Use when business rules block an action (e.g. encounter close gate failures).
    """
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict."
    default_code = "conflict"

    def __init__(self, detail=None, code=None):
        super().__init__(detail=detail or self.default_detail, code=code or self.default_code)


def _code_for(exc: Exception, http_status: int) -> str:
    if isinstance(exc, ValidationError):
        return "validation_error"
    if isinstance(exc, NotAuthenticated):
        return "not_authenticated"
    if isinstance(exc, PermissionDenied):
        return "permission_denied"
    if isinstance(exc, Http404):
        return "not_found"
    if isinstance(exc, APIException):
        return getattr(exc, "default_code", "api_error") or "api_error"
    if http_status >= 500:
        return "server_error"
    return "error"


def api_exception_handler(exc: Exception, context: dict[str, Any]):
    request = context.get("request")
    response = drf_exception_handler(exc, context)

    # Truly unhandled error
    if response is None:
        return Response(
            build_error_envelope(
                request=request,
                code="server_error",
                message="Unexpected server error.",
                details=None,
            ),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    http_status = response.status_code
    code = _code_for(exc, http_status)

    # DRF standardizes errors into response.data
    data = response.data

    # Message + details rules:
    # 1) If {"detail": "..."} only -> message=detail, details=None
    # 2) If {"detail": "...", ...} -> message=detail, details={...without detail}
    # 3) Otherwise -> message="Request failed.", details=data
    message = "Request failed."
    details = data

    if isinstance(data, dict) and "detail" in data:
        maybe_msg = data.get("detail")
        message = str(maybe_msg)
        rest = {k: v for k, v in data.items() if k != "detail"}
        details = rest or None
    elif isinstance(data, dict) and len(data) == 1 and "detail" in data:
        message = str(data.get("detail"))
        details = None

    return Response(
        build_error_envelope(
            request=request,
            code=code,
            message=message,
            details=details,
        ),
        status=http_status,
        headers=response.headers,
    )
