# backend/hm_core/facilities/services.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from hm_core.facilities.models import Facility, FacilityType


@dataclass(frozen=True)
class FacilityUpdate:
    name: Optional[str] = None
    code: Optional[str] = None
    facility_type: Optional[str] = None
    parent_facility_id: Optional[UUID] = None

    timezone: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    country: Optional[str] = None

    registration_number: Optional[str] = None
    gstin: Optional[str] = None

    is_active: Optional[bool] = None
    deactivation_reason: Optional[str] = None


class FacilityService:
    @staticmethod
    @transaction.atomic
    def create(
        *,
        tenant_id: UUID,
        name: str,
        code: str,
        facility_type: str = FacilityType.HOSPITAL,
        parent_facility_id: UUID | None = None,
        timezone_str: str = "Asia/Kolkata",
        phone: str = "",
        email: str = "",
        address_line1: str = "",
        address_line2: str = "",
        city: str = "",
        state: str = "",
        pincode: str = "",
        country: str = "India",
        registration_number: str = "",
        gstin: str = "",
    ) -> Facility:
        if facility_type not in {c for c, _ in FacilityType.choices}:
            raise ValidationError({"facility_type": "Invalid facility_type."})

        parent = None
        if parent_facility_id:
            parent = Facility.objects.filter(id=parent_facility_id, tenant_id=tenant_id).first()
            if not parent:
                raise ValidationError({"parent_facility_id": "Parent facility not found in this tenant."})

        f = Facility.objects.create(
            tenant_id=tenant_id,
            name=name,
            code=code,
            facility_type=facility_type,
            parent_facility=parent,
            timezone=timezone_str,
            phone=phone or "",
            email=email or "",
            address_line1=address_line1 or "",
            address_line2=address_line2 or "",
            city=city or "",
            state=state or "",
            pincode=pincode or "",
            country=country or "India",
            registration_number=registration_number or "",
            gstin=gstin or "",
            is_active=True,
        )
        return f

    @staticmethod
    @transaction.atomic
    def update(*, tenant_id: UUID, facility_id: UUID, patch: FacilityUpdate) -> Facility:
        f = Facility.objects.select_for_update().get(id=facility_id, tenant_id=tenant_id)

        # parent validation if provided
        if patch.parent_facility_id is not None:
            if patch.parent_facility_id == f.id:
                raise ValidationError({"parent_facility_id": "Facility cannot be its own parent."})
            if patch.parent_facility_id:
                parent = Facility.objects.filter(id=patch.parent_facility_id, tenant_id=tenant_id).first()
                if not parent:
                    raise ValidationError({"parent_facility_id": "Parent facility not found in this tenant."})
                f.parent_facility = parent
            else:
                f.parent_facility = None

        if patch.facility_type is not None:
            if patch.facility_type not in {c for c, _ in FacilityType.choices}:
                raise ValidationError({"facility_type": "Invalid facility_type."})
            f.facility_type = patch.facility_type

        # Simple field mapping
        mapping = {
            "name": patch.name,
            "code": patch.code,
            "timezone": patch.timezone,
            "phone": patch.phone,
            "email": patch.email,
            "address_line1": patch.address_line1,
            "address_line2": patch.address_line2,
            "city": patch.city,
            "state": patch.state,
            "pincode": patch.pincode,
            "country": patch.country,
            "registration_number": patch.registration_number,
            "gstin": patch.gstin,
        }
        for field, value in mapping.items():
            if value is not None:
                setattr(f, field, value)

        # activation/deactivation
        if patch.is_active is not None:
            if patch.is_active is False:
                # deactivate
                f.is_active = False
                f.deactivated_at = f.deactivated_at or timezone.now()
                if patch.deactivation_reason is not None:
                    f.deactivation_reason = patch.deactivation_reason or ""
            else:
                # reactivate
                f.is_active = True
                f.deactivated_at = None
                f.deactivation_reason = ""

        f.save()
        return f

    @staticmethod
    @transaction.atomic
    def deactivate(*, tenant_id: UUID, facility_id: UUID, reason: str = "") -> Facility:
        f = Facility.objects.select_for_update().get(id=facility_id, tenant_id=tenant_id)
        if not f.is_active:
            return f
        f.is_active = False
        f.deactivated_at = timezone.now()
        f.deactivation_reason = (reason or "").strip()
        f.save(update_fields=["is_active", "deactivated_at", "deactivation_reason", "updated_at"])
        return f
