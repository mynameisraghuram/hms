# backend/hm_core/clinical_docs/api/views.py
from __future__ import annotations

from uuid import UUID

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from hm_core.clinical_docs.api.serializers import (
    AmendSerializer,
    ClinicalDocumentSerializer,
    CreateDraftSerializer,
)
from hm_core.clinical_docs.models import DocumentStatus
from hm_core.clinical_docs.services.idempotency import get_key_from_request
from hm_core.clinical_docs.services.lifecycle import amend, create_draft, finalize
from hm_core.clinical_docs.services.read_models import (
    DEFAULT_LATEST_STATUSES,
    latest_documents_per_template_for_encounter,
)
from hm_core.iam.scope import MISSING_SCOPE_MSG, resolve_scope_from_headers


def _parse_bool(v) -> bool:
    if v is None:
        return False
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_scope_or_400(request) -> tuple[UUID | None, UUID | None, Response | None]:
    """
    Resolve (tenant_id, facility_id) from request-scoped attrs or headers.
    """
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
        return None, None, Response({"detail": MISSING_SCOPE_MSG}, status=status.HTTP_400_BAD_REQUEST)

    if scope is None:
        return None, None, Response({"detail": MISSING_SCOPE_MSG}, status=status.HTTP_400_BAD_REQUEST)

    return scope.tenant_id, scope.facility_id, None


class CreateDraftView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Clinical Docs"],
        request=CreateDraftSerializer,
        responses={201: ClinicalDocumentSerializer, 200: ClinicalDocumentSerializer},
    )
    def post(self, request, encounter_id: UUID):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        ser = CreateDraftSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        doc, created = create_draft(
            tenant_id=tenant_id,
            facility_id=facility_id,
            patient_id=ser.validated_data["patient_id"],
            encounter_id=encounter_id,
            template_code=ser.validated_data["template_code"],
            payload=ser.validated_data.get("payload") or {},
            created_by_user_id=int(getattr(request.user, "id", 0) or 0),
            idempotency_key=get_key_from_request(request),
        )

        return Response(
            ClinicalDocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class FinalizeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Clinical Docs"],
        request=None,
        responses={201: ClinicalDocumentSerializer, 200: ClinicalDocumentSerializer, 409: OpenApiTypes.OBJECT},
    )
    def post(self, request, document_id: UUID):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        try:
            doc, created = finalize(
                tenant_id=tenant_id,
                facility_id=facility_id,
                document_id=document_id,
                created_by_user_id=int(getattr(request.user, "id", 0) or 0),
                idempotency_key=get_key_from_request(request),
            )
        except ValueError as e:
            # lifecycle.finalize raises ValueError for invalid status transitions
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(
            ClinicalDocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class AmendView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Clinical Docs"],
        request=AmendSerializer,
        responses={201: ClinicalDocumentSerializer, 200: ClinicalDocumentSerializer, 409: OpenApiTypes.OBJECT},
    )
    def post(self, request, document_id: UUID):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        ser = AmendSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            doc, created = amend(
                tenant_id=tenant_id,
                facility_id=facility_id,
                document_id=document_id,
                payload_patch=ser.validated_data.get("payload_patch") or {},
                created_by_user_id=int(getattr(request.user, "id", 0) or 0),
                idempotency_key=get_key_from_request(request),
            )
        except ValueError as e:
            # lifecycle.amend raises ValueError for invalid status transitions
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(
            ClinicalDocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LatestDocumentsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Clinical Docs"],
        responses={200: ClinicalDocumentSerializer(many=True)},
        parameters=[
            OpenApiParameter(
                name="include_drafts",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Include DRAFT documents too (default false).",
            )
        ],
    )
    def get(self, request, encounter_id: UUID):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        include_drafts = _parse_bool(request.query_params.get("include_drafts"))

        statuses = DEFAULT_LATEST_STATUSES
        if include_drafts:
            statuses = (DocumentStatus.DRAFT, DocumentStatus.FINAL, DocumentStatus.AMENDED)

        qs = latest_documents_per_template_for_encounter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            statuses=statuses,
        )
        return Response(ClinicalDocumentSerializer(qs, many=True).data, status=status.HTTP_200_OK)
