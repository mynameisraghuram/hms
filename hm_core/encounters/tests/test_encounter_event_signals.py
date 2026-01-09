# backend/hm_core/encounters/tests/test_encounter_event_signals.py

import pytest

from hm_core.encounters.models import EncounterEvent

pytestmark = pytest.mark.django_db


def test_checkin_creates_event(api_client, tenant, facility, encounter):
    res = api_client.post(
        f"/api/v1/encounters/{encounter.id}/checkin/",
        {},
        format="json",
        HTTP_X_TENANT_ID=str(tenant.id),
        HTTP_X_FACILITY_ID=str(facility.id),
    )
    assert res.status_code in (200, 201), getattr(res, "data", None)

    assert EncounterEvent.objects.filter(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        code="ENCOUNTER_CHECKED_IN",
    ).exists()
