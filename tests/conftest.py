import pytest

@pytest.fixture
def tenant_id():
    return "00000000-0000-0000-0000-000000000001"

@pytest.fixture
def facility_id():
    return "00000000-0000-0000-0000-000000000101"

@pytest.fixture
def scope_headers(tenant_id, facility_id):
    return {
        "HTTP_X_TENANT_ID": tenant_id,
        "HTTP_X_FACILITY_ID": facility_id,
    }
