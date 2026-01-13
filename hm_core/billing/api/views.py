# backend/hm_core/billing/api/views.py
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from rest_framework import status, viewsets
from rest_framework.decorators import action
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
from hm_core.billing.selectors import billable_events_filtered, invoices_filtered
from hm_core.billing.services import InvoiceService, PaymentService
from hm_core.charges.selectors import get_active_charge_item
from hm_core.facilities.models import Facility, PricingTaxMode
from hm_core.iam.scope import MISSING_SCOPE_MSG, resolve_scope_from_headers

from drf_spectacular.utils import extend_schema, OpenApiParameter


def _get_scope_or_400(request) -> tuple[UUID | None, UUID | None, Response | None]:
    tenant_id = getattr(request, "tenant_id", None)
    facility_id = getattr(request, "facility_id", None)

    if not tenant_id or not facility_id:
        scope = resolve_scope_from_headers(request)
        if scope:
            tenant_id = scope.tenant_id
            facility_id = scope.facility_id

    if not tenant_id or not facility_id:
        return None, None, Response({"detail": MISSING_SCOPE_MSG}, status=status.HTTP_400_BAD_REQUEST)

    return tenant_id, facility_id, None


def _facility_tax_mode(*, tenant_id: UUID, facility_id: UUID) -> str:
    facility = (
        Facility.objects.filter(tenant_id=tenant_id, id=facility_id)
        .only("pricing_tax_mode")
        .first()
    )
    return facility.pricing_tax_mode if facility else PricingTaxMode.EXCLUSIVE


class BillableEventViewSet(viewsets.ViewSet):

    @extend_schema(
        responses={200: BillableEventSerializer(many=True)},
        tags=["Billing"],
        parameters=[
            OpenApiParameter(name="X-Tenant-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="X-Facility-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="encounter", location=OpenApiParameter.QUERY, required=False, type=str),
            OpenApiParameter(name="patient", location=OpenApiParameter.QUERY, required=False, type=str),
        ],
    )
    def list(self, request):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err:
            return err

        enc = request.query_params.get("encounter")
        pat = request.query_params.get("patient")

        encounter_id = UUID(enc) if enc else None
        patient_id = UUID(pat) if pat else None

        qs = billable_events_filtered(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            patient_id=patient_id,
        )

        return Response(BillableEventSerializer(qs, many=True).data, status=status.HTTP_200_OK)


class InvoiceViewSet(viewsets.ViewSet):
    """
    Billing v1 invoices:
    - list/retrieve
    - create draft
    - generate_from_events
    - issue
    - void
    - lines: GET/POST (manual add)
    """
    @extend_schema(
        responses={200: InvoiceSerializer(many=True)},
        tags=["Billing"],
        parameters=[
            OpenApiParameter(name="X-Tenant-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="X-Facility-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="patient", location=OpenApiParameter.QUERY, required=False, type=str),
            OpenApiParameter(name="encounter", location=OpenApiParameter.QUERY, required=False, type=str),
            OpenApiParameter(name="status", location=OpenApiParameter.QUERY, required=False, type=str),
        ],
    )

    def list(self, request):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err:
            return err

        patient = request.query_params.get("patient")
        encounter = request.query_params.get("encounter")
        status_q = request.query_params.get("status")

        qs = invoices_filtered(
            tenant_id=tenant_id,
            facility_id=facility_id,
            patient_id=UUID(patient) if patient else None,
            encounter_id=UUID(encounter) if encounter else None,
            status=status_q,
        )

        return Response(InvoiceSerializer(qs, many=True).data, status=status.HTTP_200_OK)
    
    @extend_schema(
        responses={200: InvoiceSerializer},
        tags=["Billing"],
        parameters=[
            OpenApiParameter(name="X-Tenant-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="X-Facility-Id", location=OpenApiParameter.HEADER, required=True, type=str),
        ],
    )

    def retrieve(self, request, pk=None):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err:
            return err

        inv_id = UUID(str(pk))
        inv = invoices_filtered(tenant_id=tenant_id, facility_id=facility_id).get(id=inv_id)
        return Response(InvoiceSerializer(inv).data, status=status.HTTP_200_OK)
    
    @extend_schema(
        request=InvoiceCreateSerializer,
        responses={201: InvoiceSerializer},
        tags=["Billing"],
        parameters=[
            OpenApiParameter(name="X-Tenant-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="X-Facility-Id", location=OpenApiParameter.HEADER, required=True, type=str),
        ],
    )

    def create(self, request):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err:
            return err

        ser = InvoiceCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        patient_id = ser.validated_data["patient"]
        encounter_id = ser.validated_data.get("encounter")
        notes = ser.validated_data.get("notes", "")

        inv = InvoiceService.create_draft(
            tenant_id=tenant_id,
            facility_id=facility_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
            notes=notes,
        )
        return Response(InvoiceSerializer(inv).data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        request=InvoiceGenerateFromEventsSerializer,
        responses={200: None},
        tags=["Billing"],
        parameters=[
            OpenApiParameter(name="X-Tenant-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="X-Facility-Id", location=OpenApiParameter.HEADER, required=True, type=str),
        ],
    )

    @action(detail=True, methods=["post"], url_path="generate_from_events")
    def generate_from_events(self, request, pk=None):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err:
            return err

        ser = InvoiceGenerateFromEventsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        created = InvoiceService.generate_from_billable_events(
            tenant_id=tenant_id,
            facility_id=facility_id,
            invoice_id=UUID(str(pk)),
            encounter_id=ser.validated_data.get("encounter"),
            patient_id=ser.validated_data.get("patient"),
            default_unit_price=Decimal(str(ser.validated_data.get("default_unit_price", "0.00"))),
        )
        return Response({"created_lines": created}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="issue")
    def issue(self, request, pk=None):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err:
            return err

        inv = InvoiceService.issue(
            tenant_id=tenant_id,
            facility_id=facility_id,
            invoice_id=UUID(str(pk)),
        )
        return Response(InvoiceSerializer(inv).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="void")
    def void(self, request, pk=None):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err:
            return err

        reason = ""
        if isinstance(request.data, dict):
            reason = request.data.get("reason", "") or ""

        inv = InvoiceService.void(
            tenant_id=tenant_id,
            facility_id=facility_id,
            invoice_id=UUID(str(pk)),
            reason=reason,
        )
        return Response(InvoiceSerializer(inv).data, status=status.HTTP_200_OK)
    
    @extend_schema(
        request=InvoiceLineCreateSerializer,
        responses={200: InvoiceLineSerializer(many=True), 201: InvoiceLineSerializer},
        tags=["Billing"],
        parameters=[
            OpenApiParameter(name="X-Tenant-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="X-Facility-Id", location=OpenApiParameter.HEADER, required=True, type=str),
        ],
    )

    @action(detail=True, methods=["get", "post"], url_path="lines")
    def lines(self, request, pk=None):
        """
        /billing/invoices/<invoice_id>/lines/
        - GET: list lines
        - POST: add manual line to DRAFT invoice

        Defaults:
        - If price_includes_tax is omitted, we default based on facility.pricing_tax_mode:
            * INCLUSIVE => includes tax
            * EXCLUSIVE => excludes tax
        - If tax_percent omitted and chargeable_code present, we try Charge Master tax_percent.
        """
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err:
            return err

        invoice_id = UUID(str(pk))

        if request.method.lower() == "get":
            inv = invoices_filtered(tenant_id=tenant_id, facility_id=facility_id).get(id=invoice_id)
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
                tenant_id=tenant_id,
                facility_id=facility_id,
                code=chargeable_code,
            )
            if charge:
                tax_percent = charge.tax_percent

        tax_percent = Decimal(str(tax_percent or "0.00")).quantize(Decimal("0.01"))

        if price_includes_tax is None:
            mode = _facility_tax_mode(tenant_id=tenant_id, facility_id=facility_id)
            price_includes_tax = (mode == PricingTaxMode.INCLUSIVE)

        if price_includes_tax and tax_percent > Decimal("0.00"):
            # Inclusive: compute base+tax at LINE TOTAL level to avoid 0.01 drift
            gross_line_total = (quantity * unit_price_in).quantize(Decimal("0.01"))
            divisor = (Decimal("1.00") + (tax_percent / Decimal("100.00")))

            base_line_total = (gross_line_total / divisor).quantize(Decimal("0.01"))
            tax_amount = (gross_line_total - base_line_total).quantize(Decimal("0.01"))

            base_unit_price = (base_line_total / quantity).quantize(Decimal("0.01")) if quantity > 0 else Decimal("0.00")

            line = InvoiceService.add_line(
                tenant_id=tenant_id,
                facility_id=facility_id,
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
            # Exclusive: base price + computed tax
            line = InvoiceService.add_line(
                tenant_id=tenant_id,
                facility_id=facility_id,
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
        responses={200: PaymentSerializer(many=True)},
        tags=["Billing"],
        parameters=[
            OpenApiParameter(name="X-Tenant-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="X-Facility-Id", location=OpenApiParameter.HEADER, required=True, type=str),
        ],
    )

    def get(self, request, invoice_id: UUID):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err:
            return err

        inv_id = UUID(str(invoice_id))
        inv = invoices_filtered(tenant_id=tenant_id, facility_id=facility_id).get(id=inv_id)

        payments = inv.payments.order_by("-received_at")
        return Response(PaymentSerializer(payments, many=True).data, status=status.HTTP_200_OK)
    
    @extend_schema(
        request=PaymentCreateSerializer,
        responses={201: PaymentSerializer},
        tags=["Billing"],
        parameters=[
            OpenApiParameter(name="X-Tenant-Id", location=OpenApiParameter.HEADER, required=True, type=str),
            OpenApiParameter(name="X-Facility-Id", location=OpenApiParameter.HEADER, required=True, type=str),
        ],
    )

    def post(self, request, invoice_id: UUID):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err:
            return err

        ser = PaymentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        pay = PaymentService.record_payment(
            tenant_id=tenant_id,
            facility_id=facility_id,
            invoice_id=UUID(str(invoice_id)),
            amount=Decimal(str(ser.validated_data["amount"])),
            method=ser.validated_data.get("method", "CASH"),
            reference=ser.validated_data.get("reference", ""),
            recorded_by_user_id=getattr(request.user, "id", None),
        )
        return Response(PaymentSerializer(pay).data, status=status.HTTP_201_CREATED)
