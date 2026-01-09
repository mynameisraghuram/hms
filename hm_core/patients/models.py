# backend/hm_core/patients/models.py
from django.db import models
from django.db.models import Q
from hm_core.common.models import ScopedModel


class Patient(ScopedModel):
    """
    Patient record scoped to tenant+facility for Phase 0 simplicity.
    (Later: can be tenant-level with facility-linked registrations.)
    """
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=32, blank=True)

    # facility-local medical record number
    mrn = models.CharField(max_length=64)

    class Meta:
        db_table = "patients_patient"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "facility_id", "mrn"],
                name="uq_patient_scope_mrn",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "full_name"]),
            models.Index(fields=["tenant_id", "facility_id", "phone"]),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.mrn})"
