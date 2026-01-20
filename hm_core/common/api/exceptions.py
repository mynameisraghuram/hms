# backend/hm_core/common/api/exceptions.py
from __future__ import annotations

import uuid
from typing import Any

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError, NotAuthenticated, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def _request_id(request) -> str:
    rid = getattr(request, "request_id", None)
    if not rid:
        rid = uuid.uuid4().hex
        setattr(request, "request_id", rid)
    return rid


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

    if response is None:
        rid = _request_id(request) if request else uuid.uuid4().hex
        return Response(
            {
                "error": {
                    "code": "server_error",
                    "message": "Unexpected server error.",
                    "details": None,
                    "request_id": rid,
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    rid = _request_id(request) if request else uuid.uuid4().hex
    http_status = response.status_code

    details = response.data
    if isinstance(details, dict) and "detail" in details and len(details) == 1:
        message = str(details.get("detail"))
        details = None
    else:
        message = "Request failed."

    code = _code_for(exc, http_status)

    return Response(
        {
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": rid,
            }
        },
        status=http_status,
        headers=response.headers,
    )
