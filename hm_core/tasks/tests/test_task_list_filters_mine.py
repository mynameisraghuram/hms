import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIRequestFactory, force_authenticate

from hm_core.tasks.services import TaskService
from hm_core.tasks.views import TaskViewSet

pytestmark = pytest.mark.django_db


def ensure_groups():
    for name in ["ADMIN", "DOCTOR", "NURSE", "RECEPTION", "LAB", "BILLING", "READONLY"]:
        Group.objects.get_or_create(name=name)


def make_user(username, role="DOCTOR"):
    ensure_groups()
    User = get_user_model()
    u = User.objects.create_user(username=username, password="pass123")
    u.groups.add(Group.objects.get(name=role))
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


def test_mine_filter_returns_only_tasks_assigned_to_me(encounter):
    me = make_user("me_user", role="DOCTOR")
    other = make_user("other_user", role="DOCTOR")

    t_me = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="mine-1",
        title="mine",
        assigned_to_id=me.id,
    )
    TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="mine-2",
        title="other",
        assigned_to_id=other.id,
    )

    resp = call_list(
        user=me,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        params={"mine": "1"},
    )
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.data}
    assert str(t_me.id) in ids
