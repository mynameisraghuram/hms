# backend/hm_core/patients/api/views.py
from __future__ import annotations

from uuid import UUID

from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from hm_core.common.api.pagination import paginate
from hm_core.common.permissions import PatientPermission
from hm_core.common.scope import require_scope
from hm_core.patients.api.serializers import (
    PatientCreateSerializer,
    PatientSerializer,
    PatientUpdateSerializer,
)
from hm_core.patients.models import Patient
from hm_core.patients.selectors import get_patient, search_patients
from hm_core.patients.services import PatientService


class PatientViewSet(viewsets.ViewSet):
    permission_classes = [PatientPermission]

    # drf-spectacular hints
    serializer_class = PatientSerializer
    queryset = Patient.objects.none()

    def list(self, request):
        scope = require_scope(request)

        q = request.query_params.get("q", "").strip()
        qs = search_patients(tenant_id=scope.tenant_id, facility_id=scope.facility_id, q=q)

        # Stable contract: paginated response
        return paginate(request, qs, PatientSerializer)

    def retrieve(self, request, pk=None):
        scope = require_scope(request)
        patient = get_patient(
            tenant_id=scope.tenant_id,
            facility_id=scope.facility_id,
            patient_id=UUID(str(pk)),
        )
        return Response(PatientSerializer(patient).data, status=status.HTTP_200_OK)

    def create(self, request):
        scope = require_scope(request)

        actor_user_id = request.user.id if request.user and request.user.is_authenticated else None

        ser = PatientCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            patient = PatientService.create_patient(
                tenant_id=scope.tenant_id,
                facility_id=scope.facility_id,
                actor_user_id=actor_user_id,
                **ser.validated_data,
            )
        except ValueError as e:
            # Will be wrapped by api_exception_handler
            raise DRFValidationError({"detail": str(e)})

        return Response(PatientSerializer(patient).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        scope = require_scope(request)
        actor_user_id = request.user.id if request.user and request.user.is_authenticated else None

        ser = PatientUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)

        try:
            patient = PatientService.update_patient(
                tenant_id=scope.tenant_id,
                facility_id=scope.facility_id,
                actor_user_id=actor_user_id,
                patient_id=UUID(str(pk)),
                data=ser.validated_data,
            )
        except ValueError as e:
            raise DRFValidationError({"detail": str(e)})

        return Response(PatientSerializer(patient).data, status=status.HTTP_200_OK)
