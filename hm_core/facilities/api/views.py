# backend/hm_core/facilities/api/views.py
from __future__ import annotations

from uuid import UUID

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from hm_core.facilities.api.serializers import (
    FacilityCreateSerializer,
    FacilitySerializer,
    FacilityUpdateSerializer,
)
from hm_core.facilities.models import Facility
from hm_core.facilities.selectors import facilities_for_tenant
from hm_core.facilities.services import FacilityService, FacilityUpdate


def _require_tenant_from_request(request) -> UUID:
    tenant_id = getattr(request, "tenant_id", None) or request.META.get("HTTP_X_TENANT_ID")
    if not tenant_id:
        raise PermissionDenied("Missing tenant scope. Provide X-Tenant-Id.")
    return UUID(str(tenant_id))


def _is_admin_user(request) -> bool:
    u = getattr(request, "user", None)
    return bool(u and u.is_authenticated and getattr(u, "is_superuser", False))


class FacilityViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    serializer_class = FacilitySerializer
    queryset = Facility.objects.none()

    def list(self, request):
        tenant_id = _require_tenant_from_request(request)
        active_only = request.query_params.get("active_only", "1").strip().lower() in {"1", "true", "yes", "y", "on"}
        qs = facilities_for_tenant(tenant_id=tenant_id, active_only=active_only)
        return Response(FacilitySerializer(qs, many=True).data, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        tenant_id = _require_tenant_from_request(request)
        obj = FacilityService.get(tenant_id=tenant_id, facility_id=UUID(str(pk)))
        return Response(FacilitySerializer(obj).data, status=status.HTTP_200_OK)

    def create(self, request):
        if not _is_admin_user(request):
            raise PermissionDenied("Only admin can create facilities.")

        tenant_id = _require_tenant_from_request(request)
        s = FacilityCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        obj = FacilityService.create(
            tenant_id=tenant_id,
            name=s.validated_data["name"],
            code=s.validated_data["code"],
            facility_type=s.validated_data["facility_type"],
            parent_facility_id=s.validated_data.get("parent_facility_id"),
            timezone=s.validated_data.get("timezone"),
            phone=s.validated_data.get("phone"),
            email=s.validated_data.get("email"),
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
