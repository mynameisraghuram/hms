# backend/hm_core/common/idempotency.py
from __future__ import annotations

import json
from typing import Any

from hm_core.common.models import IdempotencyRecord

HDR_IDEMPOTENCY_KEY = "HTTP_IDEMPOTENCY_KEY"


def get_key(request) -> str | None:
    return request.META.get(HDR_IDEMPOTENCY_KEY)


def load_response(tenant_id, facility_id, user_id, method: str, path: str, key: str) -> dict | None:
    """
    Load cached response payload for idempotency key.
    Supports positional args because existing views call it positionally.
    """
    rec = (
        IdempotencyRecord.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            user_id=user_id,
            method=method.upper(),
            path=path,
            idempotency_key=key,
        )
        .only("response_data")
        .first()
    )
    return rec.response_data if rec else None


def save_response(
    tenant_id,
    facility_id,
    user_id,
    method: str,
    path: str,
    key: str,
    response_data: Any,
    status_code: int = 200,
) -> None:
    """
    Persist response payload. Must be JSON-serializable.
    We stringify UUID/Decimal/datetime defensively.
    """
    safe = json.loads(json.dumps(response_data, default=str))

    IdempotencyRecord.objects.create(
        tenant_id=tenant_id,
        facility_id=facility_id,
        user_id=user_id,
        method=method.upper(),
        path=path,
        idempotency_key=key,
        status_code=int(status_code),
        response_data=safe,
    )
