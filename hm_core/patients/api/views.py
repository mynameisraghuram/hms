# backend/hm_core/patients/api/views.py
from __future__ import annotations

from uuid import UUID

from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from hm_core.common.permissions import PatientPermission
from hm_core.iam.scope import MISSING_SCOPE_MSG, resolve_scope_from_headers
from hm_core.patients.api.serializers import PatientCreateSerializer, PatientSerializer
from hm_core.patients.models import Patient
from hm_core.patients.selectors import search_patients
from hm_core.patients.services import PatientService


def _get_scope_or_400(request) -> tuple[UUID | None, UUID | None, Response | None]:
    """
    Standard scope resolver:
    - Prefer middleware-attached request.tenant_id / request.facility_id
    - Fall back to headers via resolve_scope_from_headers()
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


class PatientViewSet(viewsets.ViewSet):
    permission_classes = [PatientPermission]

    # ✅ these two lines fix spectacular + path param typing
    serializer_class = PatientSerializer
    queryset = Patient.objects.none()

    def list(self, request):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        q = request.query_params.get("q", "").strip()
        qs = search_patients(tenant_id=tenant_id, facility_id=facility_id, q=q)

        data = PatientSerializer(qs[:200], many=True).data
        return Response(data, status=status.HTTP_200_OK)

    def create(self, request):
        tenant_id, facility_id, err = _get_scope_or_400(request)
        if err is not None:
            return err

        actor_user_id = request.user.id if request.user and request.user.is_authenticated else None

        ser = PatientCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            patient = PatientService.create_patient(
                tenant_id=tenant_id,
                facility_id=facility_id,
                actor_user_id=actor_user_id,
                **ser.validated_data,
            )
        except ValueError as e:
            raise DRFValidationError({"detail": str(e)})

        return Response(PatientSerializer(patient).data, status=status.HTTP_201_CREATED)
