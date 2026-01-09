# backend/hm_core/lab/api/views.py
from __future__ import annotations

from uuid import UUID

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from hm_core.common.idempotency import get_key, load_response, save_response
from hm_core.iam.scope import MISSING_SCOPE_MSG, resolve_scope_from_headers
from hm_core.lab.api.serializers import (
    SampleReceiveSerializer,
    LabSampleSerializer,
    LabResultCreateSerializer,
    LabResultSerializer,
)
from hm_core.lab.services import LabService


def _get_scope_or_400(request) -> tuple[UUID | None, UUID | None, Response | None]:
    tenant_id = getattr(request, "tenant_id", None)
    facility_id = getattr(request, "facility_id", None)
    if tenant_id and facility_id:
        try:
            return UUID(str(tenant_id)), UUID(str(facility_id)), None
        except Exception:
            return None, None, Response({"detail": MISSING_SCOPE_MSG}, status=status.HTTP_400_BAD_REQUEST)

    try:
        scope = resolve_scope_from_headers(request)
    except Exception:
        scope = None

    if scope is None:
        return None, None, Response({"detail": MISSING_SCOPE_MSG}, status=status.HTTP_400_BAD_REQUEST)

    return scope.tenant_id, scope.facility_id, None


class LabSampleViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["post"], url_path="receive")
    def receive(self, request):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        idem = get_key(request)
        if idem:
            cached = load_response(tenant_id, facility_id, request.user.id, request.method, request.path, idem)
            if cached is not None:
                return Response(cached, status=status.HTTP_201_CREATED)

        ser = SampleReceiveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        sample = LabService.receive_sample(
            tenant_id=tenant_id,
            facility_id=facility_id,
            order_item_id=ser.validated_data["order_item_id"],
            actor_user=request.user,
            barcode=(ser.validated_data.get("barcode") or "").strip() or None,
        )

        out = LabSampleSerializer(sample).data
        if idem:
            save_response(tenant_id, facility_id, request.user.id, request.method, request.path, idem, out)

        return Response(out, status=status.HTTP_201_CREATED)


class LabResultViewSet(viewsets.ViewSet):
    def create(self, request):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        idem = get_key(request)
        if idem:
            cached = load_response(tenant_id, facility_id, request.user.id, request.method, request.path, idem)
            if cached is not None:
                return Response(cached, status=status.HTTP_201_CREATED)

        ser = LabResultCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        lr = LabService.create_result(
            tenant_id=tenant_id,
            facility_id=facility_id,
            order_item_id=ser.validated_data["order_item_id"],
            result_payload=ser.validated_data["result_payload"],
        )

        out = LabResultSerializer(lr).data
        if idem:
            save_response(tenant_id, facility_id, request.user.id, request.method, request.path, idem, out)

        return Response(out, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        try:
            lr = LabService.verify_result(
                tenant_id=tenant_id,
                facility_id=facility_id,
                lab_result_id=UUID(str(pk)),
                actor_user=request.user,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(LabResultSerializer(lr).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="release")
    def release(self, request, pk=None):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        idem = get_key(request)
        if idem:
            cached = load_response(tenant_id, facility_id, request.user.id, request.method, request.path, idem)
            if cached is not None:
                return Response(cached, status=status.HTTP_201_CREATED)

        try:
            lr = LabService.release_result(
                tenant_id=tenant_id,
                facility_id=facility_id,
                lab_result_id=UUID(str(pk)),
                actor_user=request.user,
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        out = LabResultSerializer(lr).data
        if idem:
            save_response(tenant_id, facility_id, request.user.id, request.method, request.path, idem, out)

        return Response(out, status=status.HTTP_201_CREATED)
