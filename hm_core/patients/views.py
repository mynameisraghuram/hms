# backend/hm_core/patients/views.py
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db.models import Q

from hm_core.patients.models import Patient
from hm_core.patients.serializers import PatientCreateSerializer, PatientSerializer
from hm_core.patients.services import PatientService
from hm_core.common.permissions import PatientPermission


class PatientViewSet(viewsets.ViewSet):
    permission_classes = [PatientPermission]

    def list(self, request):
        tenant_id = request.tenant_id
        facility_id = request.facility_id

        q = request.query_params.get("q", "").strip()
        qs = Patient.objects.filter(tenant_id=tenant_id, facility_id=facility_id).order_by("-created_at")

        if q:
            qs = qs.filter(
                Q(full_name__icontains=q) |
                Q(mrn__icontains=q) |
                Q(phone__icontains=q) |
                Q(email__icontains=q)
            )

        data = PatientSerializer(qs[:200], many=True).data
        return Response(data)

    def create(self, request):
        tenant_id = request.tenant_id
        facility_id = request.facility_id
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
            raise ValidationError({"detail": str(e)})

        return Response(PatientSerializer(patient).data, status=status.HTTP_201_CREATED)
