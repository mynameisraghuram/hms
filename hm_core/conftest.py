# backend/hm_core/conftest.py
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from hm_core.tenants.models import Tenant
from hm_core.facilities.models import Facility
from hm_core.patients.models import Patient
from hm_core.encounters.models import Encounter


def scope_headers(tenant, facility):
    return {
        "HTTP_X_HM_TENANT_ID": str(tenant.id),
        "HTTP_X_HM_FACILITY_ID": str(facility.id),
    }


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(code="test-tenant", name="Test Tenant")


@pytest.fixture
def facility(db, tenant):
    return Facility.objects.create(tenant=tenant, code="main", name="Main Facility")


@pytest.fixture
def user(db, tenant, facility):
    """Create a test user with ADMIN role and facility membership"""
    from hm_core.iam.models import UserProfile, Role, FacilityMembership
    
    User = get_user_model()
    user = User.objects.create_user(
        username="testuser",
        password="testpass",
        is_active=True,
    )
    
    # Create ADMIN group and assign to user
    admin_group, _ = Group.objects.get_or_create(name="ADMIN")
    user.groups.add(admin_group)
    
    # Create UserProfile
    user_profile = UserProfile.objects.create(
        user=user,
        tenant=tenant,
        is_active=True
    )
    
    # Create or get ADMIN role for tenant
    admin_role, _ = Role.objects.get_or_create(
        tenant=tenant,
        code="admin",
        defaults={"name": "Administrator", "is_active": True}
    )
    
    # Add user to facility membership
    FacilityMembership.objects.create(
        tenant=tenant,
        facility=facility,
        user_profile=user_profile,
        role=admin_role,
        is_active=True
    )
    
    return user


@pytest.fixture
def api_client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.fixture
def other_tenant(db):
    return Tenant.objects.create(code="other-tenant", name="Other Tenant")


@pytest.fixture
def other_facility(db, other_tenant):
    return Facility.objects.create(tenant=other_tenant, code="other", name="Other Facility")


@pytest.fixture
def patient(db, tenant, facility):
    return Patient.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        full_name="Test Patient",
        mrn="MRN-TEST-001",
    )


@pytest.fixture
def encounter(tenant, facility, patient, user):
    """
    IMPORTANT:
    Create encounter via EncounterService to fire domain events,
    which will create default tasks + TASK_CREATED events.
    """
    from hm_core.encounters.services import EncounterService

    enc = EncounterService.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=patient.id,
        actor_user_id=getattr(user, "id", None),
    )
    return enc