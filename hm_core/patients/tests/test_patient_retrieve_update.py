# backend/hm_core/patients/tests/test_patient_retrieve_update.py
import pytest
from hm_core.tests.helpers import scoped

pytestmark = pytest.mark.django_db


def test_patient_retrieve_ok(api_client, tenant, facility):
    create = api_client.post(
        "/api/v1/patients/",
        {"full_name": "Pat One", "mrn": "MRN-001", "phone": "9999999999"},
        format="json",
        **scoped(tenant, facility),
    )
    assert create.status_code in (200, 201), create.data
    pid = create.data["id"]

    r = api_client.get(
        f"/api/v1/patients/{pid}/",
        **scoped(tenant, facility),
    )
    assert r.status_code == 200, r.data
    assert r.data["id"] == pid
    assert r.data["mrn"] == "MRN-001"


def test_patient_patch_updates_fields(api_client, tenant, facility):
    create = api_client.post(
        "/api/v1/patients/",
        {"full_name": "Pat Two", "mrn": "MRN-002"},
        format="json",
        **scoped(tenant, facility),
    )
    assert create.status_code in (200, 201), create.data
    pid = create.data["id"]

    p = api_client.patch(
        f"/api/v1/patients/{pid}/",
        {"phone": "8888888888", "email": "pat2@example.com"},
        format="json",
        **scoped(tenant, facility),
    )
    assert p.status_code == 200, p.data
    assert p.data["phone"] == "8888888888"
    assert p.data["email"] == "pat2@example.com"


def test_patient_patch_mrn_duplicate_returns_400(api_client, tenant, facility):
    a = api_client.post(
        "/api/v1/patients/",
        {"full_name": "Pat A", "mrn": "MRN-DUP-1"},
        format="json",
        **scoped(tenant, facility),
    )
    assert a.status_code in (200, 201), a.data

    b = api_client.post(
        "/api/v1/patients/",
        {"full_name": "Pat B", "mrn": "MRN-DUP-2"},
        format="json",
        **scoped(tenant, facility),
    )
    assert b.status_code in (200, 201), b.data
    bid = b.data["id"]

    dup = api_client.patch(
        f"/api/v1/patients/{bid}/",
        {"mrn": "MRN-DUP-1"},
        format="json",
        **scoped(tenant, facility),
    )
    assert dup.status_code == 400, dup.data
    assert dup.data["error"]["code"] == "validation_error"
    # message can vary; we key off stable detail
    assert "MRN" in (dup.data["error"]["message"] + str(dup.data["error"]["details"]))
