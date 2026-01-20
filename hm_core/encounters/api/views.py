# backend/hm_core/encounters/api/views.py
from __future__ import annotations

from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ErrorDetail, ValidationError as DRFValidationError
from rest_framework.response import Response

from hm_core.common.api.exceptions import ConflictError
from hm_core.common.api.pagination import paginate
from hm_core.common.permissions import EncounterPermission
from hm_core.common.scope import require_scope
from hm_core.encounters.models import Encounter
from hm_core.encounters.selectors import EncounterSelectors
from hm_core.encounters.serializers import (
    AssessmentInputSerializer,
    EncounterCreateSerializer,
    EncounterSerializer,
    PlanInputSerializer,
    VitalsInputSerializer,
)
from hm_core.encounters.services import EncounterService


def _coerce_error_detail(value):
    if isinstance(value, ErrorDetail):
        s = str(value)
        if s == "True":
            return True
        if s == "False":
            return False
        return s

    if isinstance(value, dict):
        return {k: _coerce_error_detail(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_coerce_error_detail(v) for v in value]

    return value


def _validation_payload(exc) -> dict:
    detail = getattr(exc, "detail", None)

    if isinstance(detail, dict):
        return _coerce_error_detail(detail)
    if isinstance(detail, list):
        return {"detail": _coerce_error_detail(detail)}
    if detail is not None:
        return {"detail": _coerce_error_detail(detail)}

    message_dict = getattr(exc, "message_dict", None)
    if isinstance(message_dict, dict):
        return message_dict

    messages = getattr(exc, "messages", None)
    if messages:
        if isinstance(messages, (list, tuple)) and len(messages) == 1:
            return {"detail": messages[0]}
        return {"detail": list(messages)}

    return {"detail": str(exc)}


class EncounterViewSet(viewsets.ViewSet):
    permission_classes = [EncounterPermission]
    serializer_class = EncounterSerializer
    queryset = Encounter.objects.none()

    def get_object(self, request, pk) -> Encounter:
        scope = require_scope(request)
        return Encounter.objects.get(
            id=pk,
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
        )

    # ------------------------------------------------------------
    # CRUD-ish endpoints for frontend screens
    # ------------------------------------------------------------
    def list(self, request):
        scope = require_scope(request)

        patient_raw = request.query_params.get("patient") or request.query_params.get("patient_id")
        status_q = request.query_params.get("status")

        patient_id = None
        if patient_raw:
            patient_id = UUID(str(patient_raw))

        qs = EncounterSelectors.list_encounters(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            patient_id=patient_id,
            status=status_q,
        )
        return paginate(request, qs, EncounterSerializer)

    def retrieve(self, request, pk=None):
        enc = self.get_object(request, pk)
        return Response(EncounterSerializer(enc).data, status=status.HTTP_200_OK)

    def create(self, request):
        scope = require_scope(request)
        actor_user_id = getattr(request.user, "id", None)

        ser = EncounterCreateSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)

        try:
            enc = EncounterService.create(
                tenant_id=scope.tenant_id,
                facility_id=scope.facility_id,
                patient_id=ser.validated_data["patient_id"],
                actor_user_id=actor_user_id,
                reason=ser.validated_data.get("reason", "") or "",
                attending_doctor_id=ser.validated_data.get("attending_doctor_id", None),
                scheduled_at=ser.validated_data.get("scheduled_at", None),
            )
        except ValueError as e:
            raise DRFValidationError({"detail": str(e)})

        return Response(EncounterSerializer(enc).data, status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------
    # Existing workflow endpoints (unchanged)
    # ------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="checkin")
    def checkin(self, request, pk=None):
        scope = require_scope(request)
        enc = EncounterService.checkin(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            encounter_id=UUID(str(pk)),
            actor_user_id=getattr(request.user, "id", None),
        )
        return Response({"id": str(enc.id), "status": enc.status}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        scope = require_scope(request)
        try:
            enc = EncounterService.close(
                tenant_id=scope.tenant_id,
                facility_id=scope.facility_id,
                encounter_id=UUID(str(pk)),
                actor_user_id=getattr(request.user, "id", None),
            )
        except (DRFValidationError, DjangoValidationError) as e:
            raise ConflictError(detail=_validation_payload(e))

        return Response({"id": str(enc.id), "status": enc.status}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="close-strict")
    def close_strict(self, request, pk=None):
        scope = require_scope(request)
        try:
            enc = EncounterService.close_strict(
                tenant_id=scope.tenant_id,
                facility_id=scope.facility_id,
                encounter_id=UUID(str(pk)),
                actor_user_id=getattr(request.user, "id", None),
            )
        except (DRFValidationError, DjangoValidationError) as e:
            raise ConflictError(detail=_validation_payload(e))

        return Response({"id": str(enc.id), "status": enc.status}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="close-gate")
    def close_gate(self, request, pk=None):
        scope = require_scope(request)
        encounter_id = UUID(str(pk))

        if not Encounter.objects.filter(
            id=encounter_id,
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
        ).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        result = EncounterService.get_close_gate(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            encounter_id=encounter_id,
        )
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="vitals")
    def vitals(self, request, pk=None):
        scope = require_scope(request)
        encounter_id = UUID(str(pk))

        ser = VitalsInputSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)

        doc = EncounterService.record_vitals(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            encounter_id=encounter_id,
            authored_by_id=getattr(request.user, "id", None),
            vitals=ser.validated_data,
        )

        return Response(
            {
                "encounter_id": str(encounter_id),
                "document": {"id": str(doc.id), "kind": doc.kind, "content": doc.content},
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="assessment")
    def assessment(self, request, pk=None):
        scope = require_scope(request)
        encounter_id = UUID(str(pk))

        ser = AssessmentInputSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)

        doc = EncounterService.save_assessment(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            encounter_id=encounter_id,
            authored_by_id=getattr(request.user, "id", None),
            content=ser.validated_data,
        )

        return Response(
            {
                "encounter_id": str(encounter_id),
                "document": {"id": str(doc.id), "kind": doc.kind, "content": doc.content},
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="plan")
    def plan(self, request, pk=None):
        scope = require_scope(request)
        encounter_id = UUID(str(pk))

        ser = PlanInputSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)

        doc = EncounterService.save_plan(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            encounter_id=encounter_id,
            authored_by_id=getattr(request.user, "id", None),
            content=ser.validated_data,
        )

        return Response(
            {
                "encounter_id": str(encounter_id),
                "document": {"id": str(doc.id), "kind": doc.kind, "content": doc.content},
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="timeline")
    def timeline(self, request, pk=None):
        scope = require_scope(request)
        encounter_id = UUID(str(pk))

        if not Encounter.objects.filter(
            id=encounter_id,
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
        ).exists():
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        items = EncounterSelectors.timeline_items(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            encounter_id=encounter_id,
        )
        return Response({"encounter_id": str(encounter_id), "items": items}, status=status.HTTP_200_OK)
