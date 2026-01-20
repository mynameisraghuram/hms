import json

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory

from hm_core.common.middleware import TenantFacilityScopeMiddleware


@pytest.mark.django_db
def test_middleware_missing_scope_returns_error_envelope():
    rf = RequestFactory()
    req = rf.get("/api/v1/patients/")

    # A real User instance is authenticated; no need (and not allowed) to set is_authenticated.
    req.user = User.objects.create_user(username="u1", password="pass123")

    mw = TenantFacilityScopeMiddleware(get_response=lambda r: None)
    resp = mw.process_request(req)

    assert resp is not None
    assert resp.status_code == 400

    body = json.loads(resp.content.decode("utf-8"))
    assert "error" in body
    assert body["error"]["code"] == "validation_error"
    assert "Missing scope headers" in body["error"]["message"]
    assert "request_id" in body["error"]
