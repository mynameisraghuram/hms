# backend/hm_core/patients/services.py
from __future__ import annotations

from uuid import UUID

from django.db import IntegrityError, transaction

from hm_core.audit.services import AuditService
from hm_core.patients.models import Patient


class PatientService:
    @staticmethod
    @transaction.atomic
    def create_patient(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        actor_user_id: int | None,
        full_name: str,
        mrn: str,
        phone: str = "",
        email: str = "",
        gender: str = "",
        date_of_birth=None,
    ) -> Patient:
        try:
            patient = Patient.objects.create(
                tenant_id=tenant_id,
                facility_id=facility_id,
                full_name=full_name,
                mrn=mrn,
                phone=phone or "",
                email=email or "",
                gender=gender or "",
                date_of_birth=date_of_birth,
            )
        except IntegrityError:
            # MRN uniqueness is enforced by constraint; surface readable error.
            raise ValueError("MRN already exists for this tenant/facility.")

        AuditService.log(
            event_code="patient.created",
            entity_type="Patient",
            entity_id=patient.id,
            tenant_id=tenant_id,
            facility_id=facility_id,
            actor_user_id=actor_user_id,
            metadata={"mrn": mrn},
        )
        return patient

    @staticmethod
    @transaction.atomic
    def update_patient(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        actor_user_id: int | None,
        patient_id: UUID,
        data: dict,
    ) -> Patient:
        patient = Patient.objects.get(
            id=patient_id,
            tenant_id=tenant_id,
            facility_id=facility_id,
        )

        allowed = {"full_name", "mrn", "phone", "email", "gender", "date_of_birth"}
        updates = {k: v for k, v in (data or {}).items() if k in allowed}

        for k, v in updates.items():
            setattr(patient, k, v)

        try:
            patient.save()
        except IntegrityError:
            raise ValueError("MRN already exists for this tenant/facility.")

        AuditService.log(
            event_code="patient.updated",
            entity_type="Patient",
            entity_id=patient.id,
            tenant_id=tenant_id,
            facility_id=facility_id,
            actor_user_id=actor_user_id,
            metadata={"updated_fields": sorted(list(updates.keys()))},
        )
        return patient
