import pytest
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils.timezone import now
from rest_framework.test import APIRequestFactory, force_authenticate

from hm_core.tasks.services import TaskService
from hm_core.tasks.views import TaskViewSet
from hm_core.tasks.models import Task

pytestmark = pytest.mark.django_db


def ensure_groups():
    for name in ["ADMIN", "DOCTOR", "NURSE", "RECEPTION", "LAB", "BILLING", "READONLY"]:
        Group.objects.get_or_create(name=name)


def make_admin():
    ensure_groups()
    User = get_user_model()
    u = User.objects.create_user(username="filters_admin", password="pass123")
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


def test_overdue_filter_returns_only_open_or_in_progress_past_due(encounter):
    admin = make_admin()
    past = now() - timedelta(days=1)
    future = now() + timedelta(days=1)

    # OPEN past due -> included
    t_open_past = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-open-past",
        title="Open past",
        due_at=past,
    )

    # IN_PROGRESS past due -> included
    t_ip_past = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-ip-past",
        title="In progress past",
        due_at=past,
    )
    TaskService.start_task(tenant_id=encounter.tenant_id, facility_id=encounter.facility_id, task_id=t_ip_past.id)

    # DONE past due -> excluded (use backfill then set due_at manually)
    TaskService.backfill_mark_done(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-done-past",
    )
    t_done = Task.objects.get(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-done-past",
    )
    t_done.due_at = past
    t_done.save(update_fields=["due_at"])

    # CANCELLED past due -> excluded
    t_cancel = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-cancel-past",
        title="Cancelled past",
        due_at=past,
    )
    TaskService.cancel_task(tenant_id=encounter.tenant_id, facility_id=encounter.facility_id, task_id=t_cancel.id)

    # OPEN future due -> excluded
    TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-open-future",
        title="Open future",
        due_at=future,
    )

    # OPEN no due -> excluded
    TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-open-nodue",
        title="Open no due",
        due_at=None,
    )

    resp = call_list(
        user=admin,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        params={"overdue": "1"},
    )
    assert resp.status_code == 200

    payload = resp.data
    ids = {row["id"] for row in payload}

    assert str(t_open_past.id) in ids
    assert str(t_ip_past.id) in ids
    assert str(t_done.id) not in ids
    assert str(t_cancel.id) not in ids
