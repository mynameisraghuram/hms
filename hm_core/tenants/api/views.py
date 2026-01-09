# backend/hm_core/tenants/api/views.py
from __future__ import annotations

from uuid import UUID

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from hm_core.tenants.api.serializers import (
    TenantCreateSerializer,
    TenantMetadataUpdateSerializer,
    TenantSerializer,
    TenantStatusUpdateSerializer,
)
from hm_core.tenants.selectors import tenant_qs
from hm_core.tenants.services import TenantService


class TenantViewSet(viewsets.ViewSet):
    """
    Admin-only tenant management.
    Routing is centralized in hm_core/api/urls.py (locked standard).
    """

    permission_classes = [IsAdminUser]

    def list(self, request):
        qs = tenant_qs().order_by("-created_at")[:300]
        return Response(TenantSerializer(qs, many=True).data, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        obj = tenant_qs().get(id=UUID(str(pk)))
        return Response(TenantSerializer(obj).data, status=status.HTTP_200_OK)

    def create(self, request):
        ser = TenantCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        t = TenantService.create(
            name=ser.validated_data["name"],
            code=ser.validated_data["code"],
            status=ser.validated_data.get("status"),
            metadata=ser.validated_data.get("metadata") or {},
        )
        return Response(TenantSerializer(t).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="set-status")
    def set_status(self, request, pk=None):
        ser = TenantStatusUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        t = TenantService.set_status(tenant_id=UUID(str(pk)), status=ser.validated_data["status"])
        return Response(TenantSerializer(t).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="set-metadata")
    def set_metadata(self, request, pk=None):
        ser = TenantMetadataUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        t = TenantService.update_metadata(tenant_id=UUID(str(pk)), metadata=ser.validated_data["metadata"])
        return Response(TenantSerializer(t).data, status=status.HTTP_200_OK)
