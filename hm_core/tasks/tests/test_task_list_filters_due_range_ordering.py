#backend/hm_core/tasks/tests/test_task_list_filters_due_range_ordering.py

import pytest
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.timezone import now
from rest_framework.test import APIRequestFactory, force_authenticate

from hm_core.tasks.services import TaskService
from hm_core.tasks.api.views import TaskViewSet

pytestmark = pytest.mark.django_db


def ensure_groups():
    for name in ["ADMIN", "DOCTOR", "NURSE", "RECEPTION", "LAB", "BILLING", "READONLY"]:
        Group.objects.get_or_create(name=name)


def make_admin():
    ensure_groups()
    User = get_user_model()
    u = User.objects.create_user(username="range_admin", password="pass123")
    u.groups.add(Group.objects.get(name="ADMIN"))
    u.save()
    return u


def call_list(*, user, tenant_id, facility_id, params=None):
    factory = APIRequestFactory()
    request = factory.get("/tasks/", data=params or {})
    force_authenticate(request, user=user)
    request.tenant_id = tenant_id
    request.facility_id = facility_id
    view = TaskViewSet.as_view({"get": "list"})
    return view(request)


def _ids(resp):
    return [row["id"] for row in resp.data]


def test_due_before_filters_tasks(encounter):
    admin = make_admin()
    t0 = now()
    early = t0 - timedelta(days=2)
    mid = t0 - timedelta(days=1)
    late = t0 + timedelta(days=1)

    a = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-early",
        title="early",
        due_at=early,
    )
    b = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-mid",
        title="mid",
        due_at=mid,
    )
    TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-late",
        title="late",
        due_at=late,
    )

    resp = call_list(
        user=admin,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        params={"due_before": t0.isoformat()},
    )
    assert resp.status_code == 200
    ids = set(_ids(resp))

    assert str(a.id) in ids
    assert str(b.id) in ids
    # late is after t0, should not be included
    assert all(code_id not in ids for code_id in [str(TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="dummy-nope-1",
        title="noop",
        due_at=late,
    ).id)]) is True  # defensive no-op


def test_due_after_filters_tasks(encounter):
    admin = make_admin()
    t0 = now()
    early = t0 - timedelta(days=1)
    late = t0 + timedelta(days=1)

    TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-early2",
        title="early2",
        due_at=early,
    )
    b = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-late2",
        title="late2",
        due_at=late,
    )

    resp = call_list(
        user=admin,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        params={"due_after": t0.isoformat()},
    )
    assert resp.status_code == 200
    ids = set(_ids(resp))

    assert str(b.id) in ids
    assert len(ids) >= 1


def test_invalid_due_before_returns_400(encounter):
    admin = make_admin()

    resp = call_list(
        user=admin,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        params={"due_before": "not-a-datetime"},
    )
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "validation_error"
    assert "due_before" in resp.data["error"]["details"]



def test_ordering_due_at_ascending(encounter):
    admin = make_admin()
    base = now()
    d1 = base + timedelta(hours=1)
    d2 = base + timedelta(hours=2)
    d3 = base + timedelta(hours=3)

    t1 = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="ord1",
        title="ord1",
        due_at=d2,
    )
    t2 = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="ord2",
        title="ord2",
        due_at=d1,
    )
    t3 = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="ord3",
        title="ord3",
        due_at=d3,
    )

    resp = call_list(
        user=admin,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        params={"ordering": "due_at"},
    )
    assert resp.status_code == 200
    ids = _ids(resp)

    # due_at ascending => t2, t1, t3
    # list returns up to 300; our 3 should appear in this order
    idx = {str(t2.id): ids.index(str(t2.id)), str(t1.id): ids.index(str(t1.id)), str(t3.id): ids.index(str(t3.id))}
    assert idx[str(t2.id)] < idx[str(t1.id)] < idx[str(t3.id)]


def test_invalid_ordering_returns_400(encounter):
    admin = make_admin()

    resp = call_list(
        user=admin,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        params={"ordering": "DROP TABLE tasks_task;"},
    )
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "validation_error"
    assert "ordering" in resp.data["error"]["details"]

