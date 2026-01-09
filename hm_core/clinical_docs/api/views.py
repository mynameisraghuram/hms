# backend/hm_core/clinical_docs/api/views.py
from __future__ import annotations

from uuid import UUID

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


def _parse_bool(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


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
        return None, None, Response({"detail": MISSING_SCOPE_MSG}, status=status.HTTP_400_BAD_REQUEST)

    if scope is None:
        return None, None, Response({"detail": MISSING_SCOPE_MSG}, status=status.HTTP_400_BAD_REQUEST)

    return scope.tenant_id, scope.facility_id, None


class CreateDraftView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, encounter_id: UUID):
        ser = CreateDraftSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        user_id = int(getattr(request.user, "id", 0) or 0)

        doc, created = create_draft(
            tenant_id=tenant_id,
            facility_id=facility_id,
            patient_id=ser.validated_data["patient_id"],
            encounter_id=encounter_id,
            template_code=ser.validated_data["template_code"],
            payload=ser.validated_data.get("payload") or {},
            created_by_user_id=user_id,
            idempotency_key=get_key_from_request(request),
        )

        return Response(
            ClinicalDocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class FinalizeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id: UUID, *args, **kwargs):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        user_id = int(getattr(request.user, "id", 0) or 0)

        try:
            doc, created = finalize(
                tenant_id=tenant_id,
                facility_id=facility_id,
                document_id=document_id,
                created_by_user_id=user_id,
                idempotency_key=get_key_from_request(request),
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(
            ClinicalDocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class AmendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, document_id: UUID, *args, **kwargs):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        s = AmendSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        user_id = int(getattr(request.user, "id", 0) or 0)

        try:
            doc, created = amend(
                tenant_id=tenant_id,
                facility_id=facility_id,
                document_id=document_id,
                payload_patch=s.validated_data.get("payload_patch") or {},
                created_by_user_id=user_id,
                idempotency_key=get_key_from_request(request),
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(
            ClinicalDocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LatestDocumentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, encounter_id: UUID, *args, **kwargs):
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
