#backend/hm_core/encounters/tests/test_assessment_plan_endpoints.py
import pytest

from hm_core.tasks.models import Task
from hm_core.clinical_docs.models import EncounterDocument

pytestmark = pytest.mark.django_db


def scope_headers(tenant, facility):
    return {
        "HTTP_X_TENANT_ID": str(tenant.id),
        "HTTP_X_FACILITY_ID": str(facility.id),
    }


def test_assessment_endpoint_autocompletes_task(api_client, tenant, facility, encounter):
    url = f"/api/v1/encounters/{encounter.id}/assessment/"
    payload = {"chief_complaint": "Fever", "diagnosis": "Viral Fever"}

    resp = api_client.post(url, data=payload, format="json", **scope_headers(tenant, facility))

    assert resp.status_code == 201
    assert resp.data["document"]["kind"] == "ASSESSMENT"
    assert EncounterDocument.objects.filter(encounter_id=encounter.id, kind="ASSESSMENT").exists()

    # doctor-consult should be DONE after assessment
    task = Task.objects.get(encounter_id=encounter.id, code="doctor-consult")
    assert task.status == "DONE"
    assert task.completed_at is not None


def test_plan_endpoint_creates_doc(api_client, tenant, facility, encounter):
    url = f"/api/v1/encounters/{encounter.id}/plan/"
    payload = {
        "medications": [{"name": "Paracetamol", "dose": "500mg"}],
        "advice": "Rest and fluids",
    }

    resp = api_client.post(url, data=payload, format="json", **scope_headers(tenant, facility))

    assert resp.status_code == 201
    assert resp.data["document"]["kind"] == "PLAN"
    assert EncounterDocument.objects.filter(encounter_id=encounter.id, kind="PLAN").exists()


def test_close_gate_after_assessment_plan(api_client, tenant, facility, encounter):
    # Vitals (close gate expects it)
    api_client.post(
        f"/api/v1/encounters/{encounter.id}/vitals/",
        data={"temperature_c": 38.2, "pulse_bpm": 98},
        format="json",
        **scope_headers(tenant, facility),
    )

    # Assessment
    api_client.post(
        f"/api/v1/encounters/{encounter.id}/assessment/",
        data={"diagnosis": "Viral Fever"},
        format="json",
        **scope_headers(tenant, facility),
    )

    # Plan
    api_client.post(
        f"/api/v1/encounters/{encounter.id}/plan/",
        data={"advice": "Rest"},
        format="json",
        **scope_headers(tenant, facility),
    )

    # Close gate should pass
    resp = api_client.get(
        f"/api/v1/encounters/{encounter.id}/close-gate/",
        **scope_headers(tenant, facility),
    )

    assert resp.status_code == 200
    assert resp.data["ok"] is True
    assert resp.data["missing_tasks"] == []
    assert resp.data["missing_docs"] == []




def test_close_gate_blocks_when_all_missing(api_client, tenant, facility, encounter):
    url = f"/api/v1/encounters/{encounter.id}/close-gate/"
    resp = api_client.get(url, **scope_headers(tenant, facility))
    assert resp.status_code == 200

    # adapt to your response shape:
    assert resp.data["can_close"] is False
    assert "missing" in resp.data
    # expect it to complain about at least these:
    assert "VITALS" in resp.data["missing"]
    assert "ASSESSMENT" in resp.data["missing"]
    assert "PLAN" in resp.data["missing"]


def test_close_gate_blocks_when_tasks_not_done(api_client, tenant, facility, encounter):
    # create docs so only tasks remain
    EncounterDocument.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        kind="VITALS", content={"temperature_c": 38.2, "pulse_bpm": 98}
    )
    EncounterDocument.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        kind="ASSESSMENT", content={"chief_complaint": "Fever", "diagnosis": "Viral"}
    )
    EncounterDocument.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        kind="PLAN", content={"advice": "Rest"}
    )

    # create tasks in OPEN state
    Task.objects.filter(
    tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id, code="record-vitals"
    ).update(status="OPEN", completed_at=None)

    Task.objects.filter(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id, code="doctor-consult"
    ).update(status="OPEN", completed_at=None)


    resp = api_client.get(f"/api/v1/encounters/{encounter.id}/close-gate/", **scope_headers(tenant, facility))
    assert resp.status_code == 200
    assert resp.data["can_close"] is False
    assert "tasks_open" in resp.data["missing"] or "TASKS" in resp.data["missing"]


def test_close_gate_ok_when_docs_present_and_tasks_done(api_client, tenant, facility, encounter):
    # docs
    EncounterDocument.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        kind="VITALS", content={"temperature_c": 38.2, "pulse_bpm": 98}
    )
    EncounterDocument.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        kind="ASSESSMENT", content={"chief_complaint": "Fever", "diagnosis": "Viral"}
    )
    EncounterDocument.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        kind="PLAN", content={"advice": "Rest"}
    )

    # tasks DONE
    Task.objects.filter(
    tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id, code="record-vitals"
    ).update(status="DONE")

    Task.objects.filter(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id, code="doctor-consult"
    ).update(status="DONE")


    resp = api_client.get(f"/api/v1/encounters/{encounter.id}/close-gate/", **scope_headers(tenant, facility))
    assert resp.status_code == 200
    assert resp.data["can_close"] is True
    assert resp.data.get("missing") in ([], None)


def test_close_gate_wrong_scope_is_not_leaky(api_client, tenant, facility, encounter, other_tenant, other_facility):
    # wrong headers should not reveal encounter existence (choose your policy: 404 is best)
    resp = api_client.get(
        f"/api/v1/encounters/{encounter.id}/close-gate/",
        **scope_headers(other_tenant, other_facility),
    )
    assert resp.status_code in (403, 404)




