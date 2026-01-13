# backend/conftest.py
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from hm_core.tenants.models import Tenant
from hm_core.facilities.models import Facility
from hm_core.patients.models import Patient

from django.apps import apps

def scope_headers(tenant, facility):
    """
    Standard scope headers used by your scope resolver.
    DRF test client requires HTTP_ prefix.
    """
    return {
        "HTTP_X_TENANT_ID": str(tenant.id),
        "HTTP_X_FACILITY_ID": str(facility.id),
    }


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(code="test-tenant", name="Test Tenant")


@pytest.fixture
def facility(db, tenant):
    return Facility.objects.create(tenant=tenant, code="main", name="Main Facility")


@pytest.fixture
def user(db, tenant, facility):
    """
    Create a test user with ADMIN group + facility membership.
    Matches your membership service graph:
      auth_user -> UserProfile -> FacilityMembership
    """
    from hm_core.iam.models import UserProfile, Role, FacilityMembership

    User = get_user_model()
    user = User.objects.create_user(
        username="testuser",
        password="testpass",
        is_active=True,
    )

    admin_group, _ = Group.objects.get_or_create(name="ADMIN")
    user.groups.add(admin_group)

    user_profile = UserProfile.objects.create(
        user=user,
        tenant=tenant,
        is_active=True,
    )

    admin_role, _ = Role.objects.get_or_create(
        tenant=tenant,
        code="admin",
        defaults={"name": "Administrator", "is_active": True},
    )

    FacilityMembership.objects.create(
        tenant=tenant,
        facility=facility,
        user_profile=user_profile,
        role=admin_role,
        is_active=True,
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
    Create encounter via EncounterService to fire domain events/tasks, etc.
    """
    from hm_core.encounters.services import EncounterService

    return EncounterService.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=patient.id,
        actor_user_id=getattr(user, "id", None),
    )

# backend/hm_core/iam/tests/conftest.py





def _resolve_membership_model():
    """
    IAM tests need to delete membership rows for (user, facility).
    This project uses: User -> UserProfile -> FacilityMembership -> Facility.

    Return tuple:
      (MembershipModel, facility_field_name, mode, user_field_name)

    mode:
      - "profile:user": membership.user_profile.user_id exists
      - "direct": membership.user_id exists (fallback for other schemas)
    """
    # 1) Try the canonical model by direct import path via app registry.
    # App label is usually "iam" (because INSTALLED_APPS = "hm_core.iam")
    candidates = [
        ("iam", "FacilityMembership"),
        ("iam", "Membership"),
        ("accounts", "FacilityMembership"),
        ("accounts", "Membership"),
    ]

    for app_label, model_name in candidates:
        try:
            Model = apps.get_model(app_label, model_name)
        except Exception:
            continue

        # Must have facility FK-ish field
        if any(f.name == "facility" for f in Model._meta.fields):
            # Preferred schema: user_profile -> user
            if any(f.name == "user_profile" for f in Model._meta.fields):
                return (Model, "facility", "profile:user", "user_profile")

            # Fallback schema: direct user FK
            if any(f.name == "user" for f in Model._meta.fields):
                return (Model, "facility", "direct", "user")

    # 2) Last resort: scan *all* models loaded in Django and find something that looks right.
    for Model in apps.get_models():
        name = Model.__name__.lower()
        if "membership" not in name:
            continue

        field_names = {f.name for f in Model._meta.fields}
        if "facility" not in field_names:
            continue

        if "user_profile" in field_names:
            return (Model, "facility", "profile:user", "user_profile")
        if "user" in field_names:
            return (Model, "facility", "direct", "user")

    raise RuntimeError("No compatible Membership model found for IAM tests")

