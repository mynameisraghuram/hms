# backend/hm_core/tenants/selectors.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from django.db.models import QuerySet

from hm_core.tenants.models import Tenant, TenantStatus


def tenant_qs() -> QuerySet[Tenant]:
    return Tenant.objects.all()


def active_tenants_qs() -> QuerySet[Tenant]:
    return Tenant.objects.filter(status=TenantStatus.ACTIVE)


def get_tenant(*, tenant_id: UUID) -> Tenant:
    return Tenant.objects.get(id=tenant_id)


def get_tenant_or_none(*, tenant_id: UUID) -> Optional[Tenant]:
    return Tenant.objects.filter(id=tenant_id).first()


def get_tenant_by_code(*, code: str) -> Tenant:
    return Tenant.objects.get(code=code)


def get_tenant_by_code_or_none(*, code: str) -> Optional[Tenant]:
    return Tenant.objects.filter(code=code).first()
