# backend/hm_core/facilities/api/views.py
from __future__ import annotations

from uuid import UUID

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hm_core.facilities.api.serializers import (
    FacilityCreateSerializer,
    FacilitySerializer,
    FacilityUpdateSerializer,
)
from hm_core.facilities.selectors import facility_by_id, facilities_for_tenant
from hm_core.facilities.services import FacilityService, FacilityUpdate
from hm_core.iam.scope import MISSING_SCOPE_MSG


def _require_tenant_from_request(request) -> UUID:
    """
    Facilities are tenant-owned. We use request.tenant_id set by auth scope middleware.
    If it's missing, we return the same standardized scope error message.
    """
    tenant_id = getattr(request, "tenant_id", None) or request.META.get("HTTP_X_TENANT_ID")
    if not tenant_id:
        raise ValidationError({"detail": MISSING_SCOPE_MSG})
    return UUID(str(tenant_id))


def _is_admin_user(request) -> bool:
    """
    Temporary rule (safe by default):
    - superuser can manage facilities
    Later, replace with IAM RolePermission checks (tenant-scoped RBAC).
    """
    u = getattr(request, "user", None)
    return bool(u and u.is_authenticated and getattr(u, "is_superuser", False))


class FacilityViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        tenant_id = _require_tenant_from_request(request)
        active_only = request.query_params.get("active_only", "1").strip().lower() in {"1", "true", "yes", "y", "on"}
        qs = facilities_for_tenant(tenant_id=tenant_id, active_only=active_only)
        return Response(FacilitySerializer(qs, many=True).data, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        tenant_id = _require_tenant_from_request(request)
        try:
            obj = facility_by_id(tenant_id=tenant_id, facility_id=UUID(str(pk)))
        except Exception:
            raise NotFound("Facility not found in this tenant.")
        return Response(FacilitySerializer(obj).data, status=status.HTTP_200_OK)

    def create(self, request):
        if not _is_admin_user(request):
            raise PermissionDenied("Only admin can create facilities.")

        tenant_id = _require_tenant_from_request(request)

        s = FacilityCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        obj = FacilityService.create(
            tenant_id=tenant_id,
            name=d["name"],
            code=d["code"],
            facility_type=d.get("facility_type") or None,
            parent_facility_id=d.get("parent_facility_id"),
            timezone_str=d.get("timezone") or "Asia/Kolkata",
            phone=d.get("phone") or "",
            email=d.get("email") or "",
            address_line1=d.get("address_line1") or "",
            address_line2=d.get("address_line2") or "",
            city=d.get("city") or "",
            state=d.get("state") or "",
            pincode=d.get("pincode") or "",
            country=d.get("country") or "India",
            registration_number=d.get("registration_number") or "",
            gstin=d.get("gstin") or "",
        )
        return Response(FacilitySerializer(obj).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        if not _is_admin_user(request):
            raise PermissionDenied("Only admin can update facilities.")

        tenant_id = _require_tenant_from_request(request)

        s = FacilityUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data

        obj = FacilityService.update(
            tenant_id=tenant_id,
            facility_id=UUID(str(pk)),
            patch=FacilityUpdate(
                name=d.get("name"),
                code=d.get("code"),
                facility_type=d.get("facility_type"),
                parent_facility_id=d.get("parent_facility_id"),
                timezone=d.get("timezone"),
                phone=d.get("phone"),
                email=d.get("email"),
                address_line1=d.get("address_line1"),
                address_line2=d.get("address_line2"),
                city=d.get("city"),
                state=d.get("state"),
                pincode=d.get("pincode"),
                country=d.get("country"),
                registration_number=d.get("registration_number"),
                gstin=d.get("gstin"),
                is_active=d.get("is_active"),
                deactivation_reason=d.get("deactivation_reason"),
            ),
        )
        return Response(FacilitySerializer(obj).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        if not _is_admin_user(request):
            raise PermissionDenied("Only admin can deactivate facilities.")

        tenant_id = _require_tenant_from_request(request)
        reason = (request.data.get("reason") or "").strip()

        obj = FacilityService.deactivate(
            tenant_id=tenant_id,
            facility_id=UUID(str(pk)),
            reason=reason,
        )
        return Response(FacilitySerializer(obj).data, status=status.HTTP_200_OK)
