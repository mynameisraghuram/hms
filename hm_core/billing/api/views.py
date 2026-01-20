from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from hm_core.billing.api.serializers import (
    BillableEventSerializer,
    InvoiceCreateSerializer,
    InvoiceGenerateFromEventsSerializer,
    InvoiceLineCreateSerializer,
    InvoiceLineSerializer,
    InvoiceSerializer,
    PaymentCreateSerializer,
    PaymentSerializer,
)
from hm_core.billing.models import BillableEvent, Invoice
from hm_core.billing.selectors import billable_events_filtered, invoices_filtered
from hm_core.billing.services import InvoiceService, PaymentService
from hm_core.charges.selectors import get_active_charge_item
from hm_core.common.api.pagination import paginate
from hm_core.common.scope import require_scope
from hm_core.facilities.models import Facility, PricingTaxMode


def _uuid_or_none(value: str | None, field_name: str) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except Exception:
        raise DRFValidationError({field_name: "Invalid UUID"})


def _facility_tax_mode(*, tenant_id: UUID, facility_id: UUID) -> str:
    facility = Facility.objects.filter(tenant_id=tenant_id, id=facility_id).only("pricing_tax_mode").first()
    return facility.pricing_tax_mode if facility else PricingTaxMode.EXCLUSIVE


class BillableEventViewSet(viewsets.GenericViewSet):
    """
    Billing events (read-only in v1).
    """
    serializer_class = BillableEventSerializer
    queryset = BillableEvent.objects.none()

    @extend_schema(
        tags=["Billing"],
        responses={200: BillableEventSerializer(many=True)},
        parameters=[
            OpenApiParameter(
                name="encounter",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by encounter UUID.",
            ),
            OpenApiParameter(
                name="patient",
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by patient UUID.",
            ),
        ],
    )
    def list(self, request):
        scope = require_scope(request)

        encounter_id = _uuid_or_none(request.query_params.get("encounter"), "encounter")
        patient_id = _uuid_or_none(request.query_params.get("patient"), "patient")

        qs = billable_events_filtered(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            encounter_id=encounter_id,
            patient_id=patient_id,
        )

        return paginate(request, qs, BillableEventSerializer)


class InvoiceViewSet(viewsets.GenericViewSet):
    """
    Billing v1 invoices:
    - list/retrieve
    - create draft
    - generate_from_events
    - issue
    - void
    - lines: GET/POST (manual add)
    """
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.none()

    @extend_schema(
        tags=["Billing"],
        responses={200: InvoiceSerializer(many=True)},
        parameters=[
            OpenApiParameter(name="patient", type=OpenApiTypes.UUID, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(name="encounter", type=OpenApiTypes.UUID, location=OpenApiParameter.QUERY, required=False),
            OpenApiParameter(name="status", type=OpenApiTypes.STR, location=OpenApiParameter.QUERY, required=False),
        ],
    )
    def list(self, request):
        scope = require_scope(request)

        patient_id = _uuid_or_none(request.query_params.get("patient"), "patient")
        encounter_id = _uuid_or_none(request.query_params.get("encounter"), "encounter")
        status_q = request.query_params.get("status")

        qs = invoices_filtered(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            status=status_q,
        )

        return paginate(request, qs, InvoiceSerializer)

    @extend_schema(
        tags=["Billing"],
        responses={200: InvoiceSerializer},
    )
    def retrieve(self, request, pk=None):
        scope = require_scope(request)

        inv_id = UUID(str(pk))
        inv = invoices_filtered(tenant_id=scope.tenant_id, facility_id=scope.facility_id).get(id=inv_id)
        return Response(InvoiceSerializer(inv).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Billing"],
        request=InvoiceCreateSerializer,
        responses={201: InvoiceSerializer},
    )
    def create(self, request):
        scope = require_scope(request)

        ser = InvoiceCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        patient_id = ser.validated_data["patient"]
        encounter_id = ser.validated_data.get("encounter")
        notes = ser.validated_data.get("notes", "")

        inv = InvoiceService.create_draft(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            notes=notes,
        )
        return Response(InvoiceSerializer(inv).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Billing"],
        request=InvoiceGenerateFromEventsSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(detail=True, methods=["post"], url_path="generate_from_events")
    def generate_from_events(self, request, pk=None):
        scope = require_scope(request)

        ser = InvoiceGenerateFromEventsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        created = InvoiceService.generate_from_billable_events(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            invoice_id=UUID(str(pk)),
            encounter_id=ser.validated_data.get("encounter"),
            patient_id=ser.validated_data.get("patient"),
            default_unit_price=Decimal(str(ser.validated_data.get("default_unit_price", "0.00"))),
        )
        return Response({"created_lines": created}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Billing"],
        responses={200: InvoiceSerializer},
    )
    @action(detail=True, methods=["post"], url_path="issue")
    def issue(self, request, pk=None):
        scope = require_scope(request)

        inv = InvoiceService.issue(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            invoice_id=UUID(str(pk)),
        )
        return Response(InvoiceSerializer(inv).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Billing"],
        request=OpenApiTypes.OBJECT,
        responses={200: InvoiceSerializer},
        parameters=[
            OpenApiParameter(
                name="reason",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Optional void reason (you can also send in JSON body).",
            )
        ],
    )
    @action(detail=True, methods=["post"], url_path="void")
    def void(self, request, pk=None):
        scope = require_scope(request)

        reason = ""
        if isinstance(request.data, dict):
            reason = request.data.get("reason", "") or ""

        inv = InvoiceService.void(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            invoice_id=UUID(str(pk)),
            reason=reason,
        )
        return Response(InvoiceSerializer(inv).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Billing"],
        request=InvoiceLineCreateSerializer,
        responses={
            200: InvoiceLineSerializer(many=True),
            201: InvoiceLineSerializer,
        },
    )
    @action(detail=True, methods=["get", "post"], url_path="lines")
    def lines(self, request, pk=None):
        """
        /billing/invoices/<invoice_id>/lines/
        - GET: list lines
        - POST: add manual line to DRAFT invoice
        """
        scope = require_scope(request)
        invoice_id = UUID(str(pk))

        if request.method.lower() == "get":
            inv = invoices_filtered(tenant_id=scope.tenant_id, facility_id=scope.facility_id).get(id=invoice_id)
            qs = inv.lines.order_by("created_at")
            return Response(InvoiceLineSerializer(qs, many=True).data, status=status.HTTP_200_OK)

        ser = InvoiceLineCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        description = ser.validated_data["description"]
        chargeable_code = (ser.validated_data.get("chargeable_code") or "").strip()
        quantity = Decimal(str(ser.validated_data.get("quantity", "1.00"))).quantize(Decimal("0.01"))
        unit_price_in = Decimal(str(ser.validated_data.get("unit_price", "0.00"))).quantize(Decimal("0.01"))
        tax_percent = ser.validated_data.get("tax_percent", None)
        price_includes_tax = ser.validated_data.get("price_includes_tax", None)

        if tax_percent is None and chargeable_code:
            charge = get_active_charge_item(
                tenant_id=scope.tenant_id,
                facility_id=scope.facility_id,
                code=chargeable_code,
            )
            if charge:
                tax_percent = charge.tax_percent

        tax_percent = Decimal(str(tax_percent or "0.00")).quantize(Decimal("0.01"))

        if price_includes_tax is None:
            mode = _facility_tax_mode(tenant_id=scope.tenant_id, facility_id=scope.facility_id)
            price_includes_tax = (mode == PricingTaxMode.INCLUSIVE)

        if price_includes_tax and tax_percent > Decimal("0.00"):
            gross_line_total = (quantity * unit_price_in).quantize(Decimal("0.01"))
            divisor = (Decimal("1.00") + (tax_percent / Decimal("100.00")))

            base_line_total = (gross_line_total / divisor).quantize(Decimal("0.01"))
            tax_amount = (gross_line_total - base_line_total).quantize(Decimal("0.01"))

            base_unit_price = (base_line_total / quantity).quantize(Decimal("0.01")) if quantity > 0 else Decimal("0.00")

            line = InvoiceService.add_line(
                tenant_id=scope.tenant_id,
                facility_id=scope.facility_id,
                invoice_id=invoice_id,
                description=description,
                chargeable_code=chargeable_code,
                quantity=quantity,
                unit_price=base_unit_price,
                tax_percent=tax_percent,
                billable_event_id=None,
                line_total_override=base_line_total,
                tax_amount_override=tax_amount,
            )
        else:
            line = InvoiceService.add_line(
                tenant_id=scope.tenant_id,
                facility_id=scope.facility_id,
                invoice_id=invoice_id,
                description=description,
                chargeable_code=chargeable_code,
                quantity=quantity,
                unit_price=unit_price_in,
                tax_percent=tax_percent,
                billable_event_id=None,
            )

        return Response(InvoiceLineSerializer(line).data, status=status.HTTP_201_CREATED)


class InvoicePaymentsView(APIView):
    """
    /billing/invoices/<invoice_id>/payments/
    - GET list payments
    - POST record a payment
    """

    @extend_schema(
        tags=["Billing"],
        responses={200: PaymentSerializer(many=True)},
    )
    def get(self, request, invoice_id: UUID):
        scope = require_scope(request)

        inv_id = UUID(str(invoice_id))
        inv = invoices_filtered(tenant_id=scope.tenant_id, facility_id=scope.facility_id).get(id=inv_id)

        payments = inv.payments.order_by("-received_at")
        return Response(PaymentSerializer(payments, many=True).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["Billing"],
        request=PaymentCreateSerializer,
        responses={201: PaymentSerializer},
    )
    def post(self, request, invoice_id: UUID):
        scope = require_scope(request)

        ser = PaymentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        pay = PaymentService.record_payment(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            invoice_id=UUID(str(invoice_id)),
            amount=Decimal(str(ser.validated_data["amount"])),
            method=ser.validated_data.get("method", "CASH"),
            reference=ser.validated_data.get("reference", ""),
            recorded_by_user_id=getattr(request.user, "id", None),
        )
        return Response(PaymentSerializer(pay).data, status=status.HTTP_201_CREATED)
