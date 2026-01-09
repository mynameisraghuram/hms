import uuid
import pytest

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework.test import APIRequestFactory, force_authenticate

from hm_core.tasks.models import TaskStatus
from hm_core.tasks.services import TaskService
from hm_core.tasks.views import TaskViewSet

pytestmark = pytest.mark.django_db


# ----------------------------
# Helpers
# ----------------------------
def ensure_groups():
    for name in ["ADMIN", "DOCTOR", "NURSE", "RECEPTION", "LAB", "BILLING", "READONLY"]:
        Group.objects.get_or_create(name=name)


def make_user(username: str, role: str):
    ensure_groups()
    User = get_user_model()
    u = User.objects.create_user(username=username, password="pass123")
    u.groups.add(Group.objects.get(name=role))
    u.save()
    return u


def call_view(
    *,
    user,
    tenant_id,
    facility_id,
    action: str,
    pk: uuid.UUID | None = None,
    data: dict | None = None,
):
    """
    Call DRF ViewSet action using APIRequestFactory + force_authenticate.
    Also attaches request.tenant_id and request.facility_id to match your scope middleware.
    """
    factory = APIRequestFactory()
    data = data or {}

    if action == "list":
        view = TaskViewSet.as_view({"get": "list"})
        request = factory.get("/tasks/", data=data)
        force_authenticate(request, user=user)
        request.tenant_id = tenant_id
        request.facility_id = facility_id
        return view(request)

    if action in {"assign", "unassign", "start", "done", "reopen", "cancel"}:
        view = TaskViewSet.as_view({"post": action})
        request = factory.post(f"/tasks/{pk}/{action}/", data=data, format="json")
        force_authenticate(request, user=user)
        request.tenant_id = tenant_id
        request.facility_id = facility_id
        return view(request, pk=str(pk))

    if action == "backfill_done":
        view = TaskViewSet.as_view({"post": "backfill_done"})
        request = factory.post("/tasks/backfill-done/", data=data, format="json")
        force_authenticate(request, user=user)
        request.tenant_id = tenant_id
        request.facility_id = facility_id
        return view(request)

    raise ValueError(f"Unknown action: {action}")


# ----------------------------
# Fixtures
# ----------------------------
@pytest.fixture
def task_open(encounter):
    """
    Uses the existing 'encounter' fixture from your encounters test suite,
    which already satisfies patient_id and other NOT NULL constraints.
    """
    return TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="record-vitals",
        title="Record Vitals",
    )


# ----------------------------
# Permission matrix tests
# ----------------------------
def test_list_tasks_allowed_for_all_roles(encounter, task_open):
    admin = make_user("perm_admin_1", "ADMIN")
    doctor = make_user("perm_doctor_1", "DOCTOR")
    nurse = make_user("perm_nurse_1", "NURSE")
    reception = make_user("perm_reception_1", "RECEPTION")
    billing = make_user("perm_billing_1", "BILLING")

    for user in [admin, doctor, nurse, reception, billing]:
        resp = call_view(
            user=user,
            tenant_id=encounter.tenant_id,
            facility_id=encounter.facility_id,
            action="list",
        )
        assert resp.status_code == 200


def test_backfill_done_admin_only(encounter):
    admin = make_user("perm_admin_2", "ADMIN")
    nurse = make_user("perm_nurse_2", "NURSE")
    reception = make_user("perm_reception_2", "RECEPTION")

    payload = {"encounter_id": str(encounter.id), "code": "record-vitals"}

    resp = call_view(
        user=admin,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        action="backfill_done",
        data=payload,
    )
    assert resp.status_code == 200

    resp = call_view(
        user=nurse,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        action="backfill_done",
        data=payload,
    )
    assert resp.status_code == 403

    resp = call_view(
        user=reception,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        action="backfill_done",
        data=payload,
    )
    assert resp.status_code == 403


def test_assign_allowed_for_doctor_nurse_admin_only(encounter, task_open):
    admin = make_user("perm_admin_3", "ADMIN")
    doctor = make_user("perm_doctor_3", "DOCTOR")
    nurse = make_user("perm_nurse_3", "NURSE")
    reception = make_user("perm_reception_3", "RECEPTION")

    assignee = make_user("perm_assignee_1", "READONLY")

    # admin -> 200
    resp = call_view(
        user=admin,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        action="assign",
        pk=task_open.id,
        data={"assigned_to_id": assignee.id},
    )
    assert resp.status_code == 200

    # doctor -> 200
    resp = call_view(
        user=doctor,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        action="assign",
        pk=task_open.id,
        data={"assigned_to_id": assignee.id},
    )
    assert resp.status_code == 200

    # nurse -> 200
    resp = call_view(
        user=nurse,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        action="assign",
        pk=task_open.id,
        data={"assigned_to_id": assignee.id},
    )
    assert resp.status_code == 200

    # reception -> 403
    resp = call_view(
        user=reception,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        action="assign",
        pk=task_open.id,
        data={"assigned_to_id": assignee.id},
    )
    assert resp.status_code == 403


def test_non_clinical_assignee_can_start_and_done_own_task(encounter):
    """
    Per TaskPermission:
    - Non doctor/nurse can act on start/done/cancel/reopen ONLY if they are assignee.
    """
    reception = make_user("perm_reception_4", "RECEPTION")

    task = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="doctor-consult",
        title="Doctor consult",
        assigned_to_id=reception.id,
    )
    assert task.status == TaskStatus.OPEN

    # start -> 200 (assignee rule)
    resp = call_view(
        user=reception,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        action="start",
        pk=task.id,
    )
    assert resp.status_code == 200

    task.refresh_from_db()
    assert task.status == TaskStatus.IN_PROGRESS

    # done -> 200 (assignee rule, now IN_PROGRESS)
    resp = call_view(
        user=reception,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        action="done",
        pk=task.id,
    )
    assert resp.status_code == 200

    task.refresh_from_db()
    assert task.status == TaskStatus.DONE


def test_non_clinical_cannot_start_unassigned_task(encounter):
    reception = make_user("perm_reception_5", "RECEPTION")

    task = TaskService.create_task(
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        encounter_id=encounter.id,
        code="t-unassigned",
        title="Unassigned",
    )
    assert task.assigned_to_id is None

    resp = call_view(
        user=reception,
        tenant_id=encounter.tenant_id,
        facility_id=encounter.facility_id,
        action="start",
        pk=task.id,
    )
    assert resp.status_code == 403
