# backend/hm_core/iam/services/membership.py
from __future__ import annotations

from uuid import UUID

from hm_core.iam.models import FacilityMembership


def list_user_facilities(user_id: int) -> list[dict]:
    """
    Return facility memberships for /me response.

    Canonical membership graph:
      auth_user -> UserProfile -> FacilityMembership -> Facility (+ Tenant)
    """
    qs = (
        FacilityMembership.objects.select_related("facility", "tenant", "role", "user_profile", "user_profile__user")
        .filter(user_profile__user_id=user_id, is_active=True)
        .order_by("facility__name")
    )

    items: list[dict] = []
    for m in qs:
        f = m.facility
        t = m.tenant

        items.append(
            {
                "tenant_id": str(getattr(t, "id")),
                "tenant_code": getattr(t, "code", None),
                "facility_id": str(getattr(f, "id")),
                "facility_code": getattr(f, "code", None),
                "facility_name": getattr(f, "name", None),
                "role_code": getattr(m.role, "code", None),
                "role_name": getattr(m.role, "name", None),
                "is_primary": bool(getattr(m, "is_primary", False)),
            }
        )
    return items


def is_user_member_of_facility(*, user_id: int, tenant_id: UUID, facility_id: UUID) -> bool:
    """
    Validate user -> (tenant, facility) membership.
    This is the single source of truth used by scope enforcement.
    """
    return FacilityMembership.objects.filter(
        is_active=True,
        tenant_id=tenant_id,
        facility_id=facility_id,
        user_profile__user_id=user_id,
        user_profile__is_active=True,
    ).exists()
