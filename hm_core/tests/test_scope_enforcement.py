import json

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory

from hm_core.common.middleware import TenantFacilityScopeMiddleware


@pytest.mark.django_db
def test_middleware_invalid_scope_returns_error_envelope():
    rf = RequestFactory()
    req = rf.get(
        "/api/v1/patients/",
        **{
            "HTTP_X_TENANT_ID": "not-a-uuid",
            "HTTP_X_FACILITY_ID": "also-not-a-uuid",
        },
    )
    req.user = User.objects.create_user(username="u2", password="pass123")

    mw = TenantFacilityScopeMiddleware(get_response=lambda r: None)
    resp = mw.process_request(req)

    assert resp is not None
    assert resp.status_code == 400

    body = json.loads(resp.content.decode("utf-8"))
    assert body["error"]["code"] == "validation_error"
    assert "Invalid scope headers" in body["error"]["message"]


@pytest.mark.django_db
def test_middleware_non_member_returns_403_envelope(monkeypatch):
    # Patch membership service to force "not a member"
    monkeypatch.setattr(
        "hm_core.iam.services.membership.is_user_member_of_facility",
        lambda **kwargs: False,
        raising=True,
    )

    rf = RequestFactory()
    req = rf.get(
        "/api/v1/patients/",
        **{
            "HTTP_X_TENANT_ID": "11111111-1111-1111-1111-111111111111",
            "HTTP_X_FACILITY_ID": "22222222-2222-2222-2222-222222222222",
        },
    )
    req.user = User.objects.create_user(username="u3", password="pass123")

    mw = TenantFacilityScopeMiddleware(get_response=lambda r: None)
    resp = mw.process_request(req)

    assert resp is not None
    assert resp.status_code == 403

    body = json.loads(resp.content.decode("utf-8"))
    assert body["error"]["code"] == "permission_denied"
    assert "do not have access" in body["error"]["message"].lower()
