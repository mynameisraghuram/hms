# backend/hm_core/orders/api/views.py
from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError
from rest_framework.response import Response

from hm_core.common.idempotency import get_key, load_response, save_response
from hm_core.orders.api.serializers import OrderCreateSerializer, OrderSerializer
from hm_core.orders.models import Order
from hm_core.orders.selectors import OrderSelector
from hm_core.orders.services import OrderService


class OrderViewSet(viewsets.ViewSet):
    """
    Thin API layer:
    - scope parsing
    - idempotency caching
    - serializers validation
    - delegates writes to OrderService, reads to OrderSelector
    """

    # ✅ critical for drf-spectacular
    serializer_class = OrderSerializer
    queryset = Order.objects.none()

    def _scope_ids(self, request):
        tenant_id = getattr(request, "tenant_id", None) or request.META.get("HTTP_X_TENANT_ID")
        facility_id = getattr(request, "facility_id", None) or request.META.get("HTTP_X_FACILITY_ID")
        return tenant_id, facility_id

    def _require_scope(self, request):
        tenant_id, facility_id = self._scope_ids(request)
        if not tenant_id or not facility_id:
            raise DRFValidationError({"detail": "Missing scope headers. Provide X-Tenant-Id and X-Facility-Id."})
        return tenant_id, facility_id

    @extend_schema(
        request=OrderCreateSerializer,
        responses={201: OrderSerializer},
        tags=["Orders"],
        parameters=[
            OpenApiParameter(name="X-Tenant-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="X-Facility-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="Idempotency-Key", location=OpenApiParameter.HEADER, required=False, type=str),
        ],
        operation_id="v1_orders_create",
    )
    def create(self, request):
        tenant_id, facility_id = self._require_scope(request)

        idem = get_key(request)
        if idem:
            cached = load_response(tenant_id, facility_id, request.user.id, request.method, request.path, idem)
            if cached is not None:
                return Response(cached, status=status.HTTP_201_CREATED)

        ser = OrderCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        try:
            order, _items = OrderService.create_order(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=data["encounter_id"],
                order_type=data["order_type"],
                priority=data.get("priority"),
                items=data["items"],
            )
        except DjangoValidationError as e:
            raise DRFValidationError({"detail": str(e)})

        # Re-read with prefetch so output includes items reliably
        try:
            obj = OrderSelector.get_order(tenant_id=tenant_id, facility_id=facility_id, order_id=order.id)
        except OrderSelector.NotFound:
            raise NotFound("Order not found in this scope.")

        out = OrderSerializer(obj).data

        if idem:
            save_response(tenant_id, facility_id, request.user.id, request.method, request.path, idem, out)

        return Response(out, status=status.HTTP_201_CREATED)

    @extend_schema(
        responses={200: OrderSerializer},
        tags=["Orders"],
        parameters=[
            OpenApiParameter(name="X-Tenant-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="X-Facility-Id", location=OpenApiParameter.HEADER, required=True, type=str),
        ],
        operation_id="v1_orders_retrieve",
    )
    def retrieve(self, request, pk=None):
        tenant_id, facility_id = self._require_scope(request)
        try:
            obj = OrderSelector.get_order(tenant_id=tenant_id, facility_id=facility_id, order_id=pk)
        except OrderSelector.NotFound:
            raise NotFound("Order not found in this scope.")
        return Response(OrderSerializer(obj).data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={200: OrderSerializer(many=True)},
        tags=["Orders"],
        parameters=[
            OpenApiParameter(name="X-Tenant-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="X-Facility-Id", location=OpenApiParameter.HEADER, required=True, type=str),
        ],
        operation_id="v1_orders_list",
    )
    def list(self, request):
        tenant_id, facility_id = self._require_scope(request)
        encounter_id = request.query_params.get("encounter")
        qs = OrderSelector.list_orders(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
        )
        return Response(OrderSerializer(qs, many=True).data, status=status.HTTP_200_OK)
