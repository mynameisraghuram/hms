# backend/hm_core/common/idempotency.py
from __future__ import annotations

import threading
from django.conf import settings
from django.db import IntegrityError, transaction

from hm_core.common.models import IdempotencyRecord

_LOCK = threading.Lock()
_STORE = {}  # legacy in-memory store


def _use_db() -> bool:
    """
    Default False so tests/dev stay unchanged.
    Enable in production with:
        COMMON_IDEMPOTENCY_USE_DB = True
    """
    return bool(getattr(settings, "COMMON_IDEMPOTENCY_USE_DB", False))


def get_key(request):
    # In DRF test client: "HTTP_IDEMPOTENCY_KEY" becomes request.META["HTTP_IDEMPOTENCY_KEY"]
    return request.META.get("HTTP_IDEMPOTENCY_KEY")


def _norm(tenant_id, facility_id, user_id, method, path, key):
    return (str(tenant_id), str(facility_id), str(user_id), method.upper(), path, str(key))


def load_response(tenant_id, facility_id, user_id, method, path, key):
    if not key:
        return None

    if not _use_db():
        with _LOCK:
            return _STORE.get(_norm(tenant_id, facility_id, user_id, method, path, key))

    rec = (
        IdempotencyRecord.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            user_id=int(user_id),
            method=method.upper(),
            path=path,
            idempotency_key=str(key),
        )
        .order_by("-created_at")
        .first()
    )
    return None if rec is None else rec.response_data


def save_response(tenant_id, facility_id, user_id, method, path, key, response_data, status_code: int = 200):
    if not key:
        return

    if not _use_db():
        with _LOCK:
            _STORE[_norm(tenant_id, facility_id, user_id, method, path, key)] = response_data
        return

    # DB-backed: safe under concurrency
    try:
        with transaction.atomic():
            IdempotencyRecord.objects.create(
                tenant_id=tenant_id,
                facility_id=facility_id,
                user_id=int(user_id),
                method=method.upper(),
                path=path,
                idempotency_key=str(key),
                status_code=int(status_code),
                response_data=response_data,
            )
    except IntegrityError:
        # already saved by a concurrent request — ignore
        return
