# backend/hm_core/rules/tests/test_close_gate.py
import pytest
from hm_core.rules.models import Rule
from hm_core.rules.services import RuleEngine
from hm_core.tasks.models import Task, TaskStatus
from hm_core.clinical_docs.models import EncounterDocument


pytestmark = pytest.mark.django_db


def seed_close_gate_rule(tenant_id, facility_id):
    Rule.objects.update_or_create(
        tenant_id=tenant_id,
        facility_id=facility_id,
        code="encounter.close_gate",
        defaults={
            "description": "Encounter close gate for Phase 0 OPD",
            "is_active": True,
            "config": {
                "required_tasks": ["record-vitals", "doctor-consult"],
                "required_docs": ["ASSESSMENT", "PLAN"],
            },
        },
    )


def test_close_gate_all_missing(tenant, facility, encounter):
    seed_close_gate_rule(tenant.id, facility.id)

    res = RuleEngine.evaluate_encounter_close_gate(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id
    )
    assert res.ok is False
    assert set(res.missing_tasks) == {"record-vitals", "doctor-consult"}
    assert set(res.missing_docs) == {"ASSESSMENT", "PLAN"}


def test_close_gate_tasks_done_docs_missing(tenant, facility, encounter):
    seed_close_gate_rule(tenant.id, facility.id)

    Task.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        code="record-vitals", title="Record Vitals", status=TaskStatus.DONE
    )
    Task.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        code="doctor-consult", title="Doctor Consult", status=TaskStatus.DONE
    )

    res = RuleEngine.evaluate_encounter_close_gate(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id
    )
    assert res.ok is False
    assert res.missing_tasks == []
    assert set(res.missing_docs) == {"ASSESSMENT", "PLAN"}


def test_close_gate_docs_present_tasks_missing(tenant, facility, encounter):
    seed_close_gate_rule(tenant.id, facility.id)

    EncounterDocument.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        kind="ASSESSMENT", content={"x": 1}, authored_by_id=None
    )
    EncounterDocument.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        kind="PLAN", content={"y": 2}, authored_by_id=None
    )

    res = RuleEngine.evaluate_encounter_close_gate(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id
    )
    assert res.ok is False
    assert set(res.missing_tasks) == {"record-vitals", "doctor-consult"}
    assert res.missing_docs == []


def test_close_gate_ok(tenant, facility, encounter):
    seed_close_gate_rule(tenant.id, facility.id)

    Task.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        code="record-vitals", title="Record Vitals", status=TaskStatus.DONE
    )
    Task.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        code="doctor-consult", title="Doctor Consult", status=TaskStatus.DONE
    )
    EncounterDocument.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        kind="ASSESSMENT", content={"x": 1}, authored_by_id=None
    )
    EncounterDocument.objects.create(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id,
        kind="PLAN", content={"y": 2}, authored_by_id=None
    )

    res = RuleEngine.evaluate_encounter_close_gate(
        tenant_id=tenant.id, facility_id=facility.id, encounter_id=encounter.id
    )
    assert res.ok is True
    assert res.missing_tasks == []
    assert res.missing_docs == []
