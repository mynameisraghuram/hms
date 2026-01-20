# backend/hm_core/encounters/tests/test_encounter_list_create_retrieve.py
import pytest
from hm_core.tests.helpers import scoped

pytestmark = pytest.mark.django_db


def _create_patient(api_client, tenant, facility, mrn: str):
    r = api_client.post(
        "/api/v1/patients/",
        {"full_name": f"Patient {mrn}", "mrn": mrn},
        format="json",
        **scoped(tenant, facility),
    )
    assert r.status_code in (200, 201), r.data
    return r.data["id"]


def test_encounter_create_and_retrieve(api_client, tenant, facility):
    patient_id = _create_patient(api_client, tenant, facility, "MRN-E-001")

    c = api_client.post(
        "/api/v1/encounters/",
        {"patient_id": patient_id, "reason": "Fever"},
        format="json",
        **scoped(tenant, facility),
    )
    assert c.status_code in (200, 201), c.data
    enc_id = c.data["id"]

    r = api_client.get(
        f"/api/v1/encounters/{enc_id}/",
        **scoped(tenant, facility),
    )
    assert r.status_code == 200, r.data
    assert str(r.data["id"]) == str(enc_id)
    assert str(r.data["patient_id"]) == str(patient_id)


def test_encounter_create_duplicate_active_blocks_400(api_client, tenant, facility):
    patient_id = _create_patient(api_client, tenant, facility, "MRN-E-002")

    c1 = api_client.post(
        "/api/v1/encounters/",
        {"patient_id": patient_id, "reason": "Visit 1"},
        format="json",
        **scoped(tenant, facility),
    )
    assert c1.status_code in (200, 201), c1.data

    c2 = api_client.post(
        "/api/v1/encounters/",
        {"patient_id": patient_id, "reason": "Visit 2"},
        format="json",
        **scoped(tenant, facility),
    )
    assert c2.status_code == 400, c2.data
    assert c2.data["error"]["code"] == "validation_error"


def test_encounter_list_paginated_and_filter_by_patient(api_client, tenant, facility):
    p1 = _create_patient(api_client, tenant, facility, "MRN-E-003")
    p2 = _create_patient(api_client, tenant, facility, "MRN-E-004")

    e1 = api_client.post(
        "/api/v1/encounters/",
        {"patient_id": p1, "reason": "P1 visit"},
        format="json",
        **scoped(tenant, facility),
    )
    assert e1.status_code in (200, 201), e1.data

    e2 = api_client.post(
        "/api/v1/encounters/",
        {"patient_id": p2, "reason": "P2 visit"},
        format="json",
        **scoped(tenant, facility),
    )
    assert e2.status_code in (200, 201), e2.data

    all_list = api_client.get(
        "/api/v1/encounters/",
        **scoped(tenant, facility),
    )
    assert all_list.status_code == 200, all_list.data
    assert isinstance(all_list.data, dict) and "results" in all_list.data, all_list.data
    assert all_list.data["count"] >= 2

    filt = api_client.get(
        f"/api/v1/encounters/?patient={p1}",
        **scoped(tenant, facility),
    )
    assert filt.status_code == 200, filt.data
    assert filt.data["count"] == 1, filt.data
    assert str(filt.data["results"][0]["patient_id"]) == str(p1)
