# backend/hm_core/iam/tests/test_session_bootstrap.py
import pytest

pytestmark = pytest.mark.django_db


def test_session_bootstrap_requires_auth():
    from rest_framework.test import APIClient

    c = APIClient()
    res = c.get("/api/session/bootstrap/")
    assert res.status_code in (401, 403)


def test_session_bootstrap_returns_default_scope(api_client, user):
    # api_client fixture is authenticated already, no scope headers sent
    res = api_client.get("/api/session/bootstrap/")
    assert res.status_code == 200

    body = res.json()
    assert "user" in body
    assert body["user"]["id"] == user.id
    assert "memberships" in body
    assert "active_scope" in body

    # user fixture creates a facility membership, so active_scope should exist
    assert body["active_scope"] is not None
    assert "tenant_id" in body["active_scope"]
    assert "facility_id" in body["active_scope"]


def test_session_bootstrap_accepts_scope_headers(api_client, tenant, facility):
    res = api_client.get(
        "/api/session/bootstrap/",
        **{
            "HTTP_X_TENANT_ID": str(tenant.id),
            "HTTP_X_FACILITY_ID": str(facility.id),
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["active_scope"]["tenant_id"] == str(tenant.id)
    assert body["active_scope"]["facility_id"] == str(facility.id)
