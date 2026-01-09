# backend/hm_core/common/models.py
from __future__ import annotations

import uuid
from django.db import models


class TimeStampedModel(models.Model):
    """
    Standard timestamps for all entities.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ScopedModel(TimeStampedModel):
    """
    Enforces multi-tenant + multi-facility scope at the data layer.
    (Middleware enforces request scope; this enforces persistence scope.)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant_id = models.UUIDField(db_index=True)
    facility_id = models.UUIDField(db_index=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["tenant_id", "facility_id"], name="scoped_tenant_facility_idx"),
        ]


# -------------------------------------------------------------------
# ✅ Durable idempotency (production-safe)
# -------------------------------------------------------------------

class IdempotencyRecord(TimeStampedModel):
    """
    Stores idempotent responses durably.

    Keyed by:
      (tenant_id, facility_id, user_id, method, path, idempotency_key)

    This makes POST/PUT operations safe across:
      - multiple workers
      - multiple pods
      - restarts
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant_id = models.UUIDField(db_index=True)
    facility_id = models.UUIDField(db_index=True)

    # request identity
    user_id = models.BigIntegerField(db_index=True)
    method = models.CharField(max_length=16, db_index=True)
    path = models.CharField(max_length=255, db_index=True)
    idempotency_key = models.CharField(max_length=255, db_index=True)

    # stored response
    status_code = models.PositiveIntegerField(default=200)
    response_data = models.JSONField(default=dict)

    class Meta:
        db_table = "common_idempotency_record"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "facility_id", "user_id", "method", "path", "idempotency_key"],
                name="uq_idempo_scope_user_method_path_key",
            )
        ]
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.method} {self.path} {self.idempotency_key}"
