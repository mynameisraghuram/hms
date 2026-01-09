# backend/hm_core/clinical_docs/tests/test_latest_docs_api.py

import uuid
import pytest
from django.urls import reverse

from hm_core.clinical_docs.models import ClinicalDocument, DocumentStatus


pytestmark = [pytest.mark.django_db]


def _scope_headers(tenant_id, facility_id):
    # matches _scope_ids() fallback behavior
    return {
        "HTTP_X_TENANT_ID": str(tenant_id),
        "HTTP_X_FACILITY_ID": str(facility_id),
    }


def test_latest_endpoint_returns_one_per_template_highest_version(api_client, tenant, facility, encounter):
    # template A: v1 FINAL, v2 AMENDED -> should return v2
    ClinicalDocument.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=uuid.uuid4(),
        encounter_id=encounter.id,
        template_code="SOAP",
        version=1,
        status=DocumentStatus.FINAL,
        payload={"v": 1},
        created_by_user_id=1,
    )
    ClinicalDocument.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=uuid.uuid4(),
        encounter_id=encounter.id,
        template_code="SOAP",
        version=2,
        status=DocumentStatus.AMENDED,
        payload={"v": 2},
        created_by_user_id=1,
    )

    # template B: v1 FINAL only -> should return v1
    ClinicalDocument.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=uuid.uuid4(),
        encounter_id=encounter.id,
        template_code="DISCHARGE",
        version=1,
        status=DocumentStatus.FINAL,
        payload={"b": 1},
        created_by_user_id=1,
    )

    url = reverse("clinical_docs:clinical-doc-latest-per-template", kwargs={"encounter_id": encounter.id})
    res = api_client.get(url, **_scope_headers(tenant.id, facility.id))

    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert {row["template_code"] for row in data} == {"SOAP", "DISCHARGE"}

    soap = next(row for row in data if row["template_code"] == "SOAP")
    assert soap["version"] == 2
    assert soap["status"] == DocumentStatus.AMENDED


def test_latest_endpoint_ignores_drafts_by_default(api_client, tenant, facility, encounter):
    ClinicalDocument.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=uuid.uuid4(),
        encounter_id=encounter.id,
        template_code="OPNOTE",
        version=1,
        status=DocumentStatus.DRAFT,
        payload={"draft": True},
        created_by_user_id=1,
    )

    url = reverse("clinical_docs:clinical-doc-latest-per-template", kwargs={"encounter_id": encounter.id})
    res = api_client.get(url, **_scope_headers(tenant.id, facility.id))

    assert res.status_code == 200
    assert res.json() == []


def test_latest_endpoint_can_include_drafts(api_client, tenant, facility, encounter):
    ClinicalDocument.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        patient_id=uuid.uuid4(),
        encounter_id=encounter.id,
        template_code="OPNOTE",
        version=1,
        status=DocumentStatus.DRAFT,
        payload={"draft": True},
        created_by_user_id=1,
    )

    url = reverse("clinical_docs:clinical-doc-latest-per-template", kwargs={"encounter_id": encounter.id})
    res = api_client.get(url + "?include_drafts=true", **_scope_headers(tenant.id, facility.id))

    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["template_code"] == "OPNOTE"
    assert data[0]["status"] == DocumentStatus.DRAFT


def test_latest_endpoint_requires_scope_headers(api_client, encounter):
    url = reverse("clinical_docs:clinical-doc-latest-per-template", kwargs={"encounter_id": encounter.id})
    res = api_client.get(url)
    assert res.status_code == 400
    # Updated to match the actual middleware error message
    assert res.json()["detail"] == "Missing scope headers. Provide X-Tenant-Id and X-Facility-Id."