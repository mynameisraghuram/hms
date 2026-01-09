# backend/hm_core/encounters/management/commands/create_test_encounter.py
import uuid
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from hm_core.tenants.models import Tenant
from hm_core.facilities.models import Facility
from hm_core.patients.models import Patient
from hm_core.encounters.models import Encounter


class Command(BaseCommand):
    help = "Create a test encounter (and fresh patient) to force signals and events."

    def handle(self, *args, **options):
        tenant = Tenant.objects.first()
        facility = Facility.objects.first()
        User = get_user_model()
        user = User.objects.first()

        if not tenant or not facility or not user:
            self.stderr.write("Need at least 1 Tenant, Facility, User in DB.")
            return

        # Always make a new patient to avoid uq_active_encounter_per_patient_scope
        mrn = f"MRN-{uuid.uuid4().hex[:8].upper()}"
        patient = Patient.objects.create(
            tenant_id=tenant.id,
            facility_id=facility.id,
            full_name="Signal Test Patient",
            mrn=mrn,
        )

        enc = Encounter.objects.create(
            tenant_id=tenant.id,
            facility_id=facility.id,
            patient_id=patient.id,
            created_by=user,
            status="CREATED",
        )

        self.stdout.write(self.style.SUCCESS(f"Created encounter={enc.id} patient={patient.id} mrn={mrn}"))
