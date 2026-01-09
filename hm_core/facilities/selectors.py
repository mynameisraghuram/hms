# backend/hm_core/facilities/selectors.py
from __future__ import annotations

from uuid import UUID

from django.db.models import QuerySet

from hm_core.facilities.models import Facility


def facilities_for_tenant(*, tenant_id: UUID, active_only: bool = True) -> QuerySet[Facility]:
    qs = Facility.objects.filter(tenant_id=tenant_id)
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.order_by("name")


def facility_by_id(*, tenant_id: UUID, facility_id: UUID) -> Facility:
    return Facility.objects.get(id=facility_id, tenant_id=tenant_id)


def child_facilities(*, tenant_id: UUID, parent_facility_id: UUID, active_only: bool = True) -> QuerySet[Facility]:
    qs = Facility.objects.filter(tenant_id=tenant_id, parent_facility_id=parent_facility_id)
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.order_by("name")
