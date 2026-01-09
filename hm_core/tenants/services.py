# backend/hm_core/tenants/services.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from django.db import transaction
from rest_framework.exceptions import ValidationError

from hm_core.tenants.models import Tenant, TenantStatus


class TenantService:
    """
    All Tenant mutations live here (write-model boundary).
    """

    @staticmethod
    @transaction.atomic
    def create(
        *,
        name: str,
        code: str,
        metadata: Optional[dict] = None,
        status: str = TenantStatus.ACTIVE,
    ) -> Tenant:
        code = (code or "").strip()
        name = (name or "").strip()

        if not code:
            raise ValidationError({"code": "This field is required."})
        if not name:
            raise ValidationError({"name": "This field is required."})

        if status not in TenantStatus.values:
            raise ValidationError({"status": f"Invalid status. Allowed: {list(TenantStatus.values)}"})

        obj = Tenant.objects.create(
            name=name,
            code=code,
            status=status,
            metadata=metadata or {},
        )
        return obj

    @staticmethod
    @transaction.atomic
    def update_metadata(*, tenant_id: UUID, metadata: dict) -> Tenant:
        if metadata is None or not isinstance(metadata, dict):
            raise ValidationError({"metadata": "Must be a JSON object."})

        t = Tenant.objects.select_for_update().get(id=tenant_id)
        t.metadata = metadata
        t.save(update_fields=["metadata", "updated_at"])
        return t

    @staticmethod
    @transaction.atomic
    def set_status(*, tenant_id: UUID, status: str) -> Tenant:
        if status not in TenantStatus.values:
            raise ValidationError({"status": f"Invalid status. Allowed: {list(TenantStatus.values)}"})

        t = Tenant.objects.select_for_update().get(id=tenant_id)

        # idempotent no-op
        if t.status == status:
            return t

        t.status = status
        t.save(update_fields=["status", "updated_at"])
        return t

    @staticmethod
    def suspend(*, tenant_id: UUID) -> Tenant:
        return TenantService.set_status(tenant_id=tenant_id, status=TenantStatus.SUSPENDED)

    @staticmethod
    def reactivate(*, tenant_id: UUID) -> Tenant:
        return TenantService.set_status(tenant_id=tenant_id, status=TenantStatus.ACTIVE)

    @staticmethod
    def soft_delete(*, tenant_id: UUID) -> Tenant:
        # soft delete only; real delete is dangerous in multi-tenant audit systems
        return TenantService.set_status(tenant_id=tenant_id, status=TenantStatus.DELETED)
