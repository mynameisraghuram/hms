# backend/hm_core/encounters/tests/test_close_strict_endpoint.py

import pytest
from django.utils import timezone
from rest_framework.exceptions import ErrorDetail

from hm_core.clinical_docs.models import EncounterDocument
from hm_core.tasks.models import Task, TaskStatus

pytestmark = pytest.mark.django_db


def _scope(tenant, facility):
    return {"HTTP_X_TENANT_ID": str(tenant.id), "HTTP_X_FACILITY_ID": str(facility.id)}


def _coerce(value):
    """
    DRF sometimes stores booleans as ErrorDetail("True"/"False") inside nested structures.
    Convert them back to real Python bools for stable assertions.
    """
    if isinstance(value, ErrorDetail):
        s = str(value)
        if s == "True":
            return True
        if s == "False":
            return False
        return s

    if isinstance(value, dict):
        return {k: _coerce(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [_coerce(v) for v in value]

    return value


def _conflict_details(res):
    """
    Bundle-1: 409 errors are wrapped in the standard envelope:
      {"error": {"code": "...", "message": "...", "details": {...}}}
    """
    assert isinstance(res.data, dict) and "error" in res.data, res.data
    err = res.data["error"]
    assert isinstance(err, dict), res.data
    return _coerce(err.get("details") or {})


def test_close_strict_blocks_when_missing_completeness(api_client, tenant, facility, encounter):
    # encounter fixture has tasks OPEN by default and no docs, so completeness must fail
    res = api_client.post(
        f"/api/v1/encounters/{encounter.id}/close-strict/",
        {},
        format="json",
        **_scope(tenant, facility),
    )
    assert res.status_code == 409, res.data

    details = _conflict_details(res)

    assert details.get("can_close") is False
    assert details.get("ok") is False
    assert "missing" in details

    # expected missing includes docs_missing/tasks_open in your current shape
    missing = details["missing"]
    assert missing.get("DOCS") is True
    assert missing.get("TASKS") is True


def test_close_strict_allows_when_complete(api_client, tenant, facility, encounter):
    # Create required docs (VITALS, ASSESSMENT, PLAN)
    EncounterDocument.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        kind="VITALS",
        content={"temperature_c": 38.2, "pulse_bpm": 98},
    )
    EncounterDocument.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        kind="ASSESSMENT",
        content={"diagnosis": "Viral Fever"},
    )
    EncounterDocument.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        kind="PLAN",
        content={"advice": "Rest"},
    )

    # Mark required tasks DONE
    Task.objects.filter(
        tenant_id=tenant.id,
        facility_id=facility.id,
        encounter_id=encounter.id,
        code__in=["record-vitals", "doctor-consult"],
    ).update(status=TaskStatus.DONE, completed_at=timezone.now())

    res = api_client.post(
        f"/api/v1/encounters/{encounter.id}/close-strict/",
        {},
        format="json",
        **_scope(tenant, facility),
    )
    assert res.status_code in (200, 201), res.data
    assert res.data.get("status") == "CLOSED"
