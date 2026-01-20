from __future__ import annotations

from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from hm_core.common.api.pagination import paginate
from hm_core.common.permissions import PatientPermission
from hm_core.common.scope import require_scope
from hm_core.patients.api.serializers import PatientCreateSerializer, PatientSerializer
from hm_core.patients.models import Patient
from hm_core.patients.selectors import search_patients
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
