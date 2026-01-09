# backend/hm_core/tasks/api/views.py
from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError
from rest_framework.response import Response

from hm_core.tasks.api.serializers import TaskSerializer
from hm_core.tasks.permissions import TaskPermission
from hm_core.tasks.selectors import TaskSelector
from hm_core.tasks.services import TaskService


class TaskViewSet(viewsets.ViewSet):
    """
    Thin API layer:
    - scope parsing
    - validation mapping
    - calls selectors for reads
    - calls services for writes
    """

    permission_classes = [TaskPermission]

    def _scope_ids(self, request):
        """
        Prefer request.tenant_id / request.facility_id if middleware/auth set them.
        Otherwise fall back to headers so tests still work when middleware is disabled.
        """
        tenant_id = getattr(request, "tenant_id", None) or request.META.get("HTTP_X_TENANT_ID")
        facility_id = getattr(request, "facility_id", None) or request.META.get("HTTP_X_FACILITY_ID")
        return tenant_id, facility_id

    def _require_scope(self, request):
        tenant_id, facility_id = self._scope_ids(request)
        if not tenant_id or not facility_id:
            raise DRFValidationError({"detail": "Missing scope headers. Provide X-Tenant-Id and X-Facility-Id."})
        return tenant_id, facility_id

    def _get_object(self, request, pk):
        tenant_id, facility_id = self._require_scope(request)
        try:
            return TaskSelector.get_task(tenant_id=tenant_id, facility_id=facility_id, task_id=pk)
        except TaskSelector.NotFound:
            raise NotFound("Task not found in this scope.")

    # ----------------------------
    # Reads
    # ----------------------------
    def list(self, request):
        tenant_id, facility_id = self._require_scope(request)

        try:
            qs = TaskSelector.list_tasks(
                tenant_id=tenant_id,
                facility_id=facility_id,
                user_id=getattr(request.user, "id", None),
                params=request.query_params,
            )
        except DjangoValidationError as e:
            raise DRFValidationError({"detail": e.message if hasattr(e, "message") else str(e)})

        return Response(TaskSerializer(qs[:300], many=True).data)

    # ----------------------------
    # Workflow / assignment actions
    # ----------------------------
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        task = self._get_object(request, pk)
        self.check_object_permissions(request, task)

        assigned_to_id = request.data.get("assigned_to_id")
        if not assigned_to_id:
            raise DRFValidationError({"assigned_to_id": "This field is required."})

        try:
            TaskService.assign_task(
                tenant_id=task.tenant_id,
                facility_id=task.facility_id,
                task_id=task.id,
                assigned_to_id=int(assigned_to_id),
            )
        except DjangoValidationError as e:
            raise DRFValidationError({"detail": str(e)})

        task.refresh_from_db()
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def unassign(self, request, pk=None):
        task = self._get_object(request, pk)
        self.check_object_permissions(request, task)

        try:
            TaskService.unassign_task(
                tenant_id=task.tenant_id,
                facility_id=task.facility_id,
                task_id=task.id,
            )
        except DjangoValidationError as e:
            raise DRFValidationError({"detail": str(e)})

        task.refresh_from_db()
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        task = self._get_object(request, pk)
        self.check_object_permissions(request, task)

        try:
            TaskService.start_task(
                tenant_id=task.tenant_id,
                facility_id=task.facility_id,
                task_id=task.id,
            )
        except DjangoValidationError as e:
            raise DRFValidationError({"detail": str(e)})

        task.refresh_from_db()
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def done(self, request, pk=None):
        task = self._get_object(request, pk)
        self.check_object_permissions(request, task)

        try:
            TaskService.complete_task(
                tenant_id=task.tenant_id,
                facility_id=task.facility_id,
                task_id=task.id,
            )
        except DjangoValidationError as e:
            raise DRFValidationError({"detail": str(e)})

        task.refresh_from_db()
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        task = self._get_object(request, pk)
        self.check_object_permissions(request, task)

        try:
            TaskService.reopen_task(
                tenant_id=task.tenant_id,
                facility_id=task.facility_id,
                task_id=task.id,
            )
        except DjangoValidationError as e:
            raise DRFValidationError({"detail": str(e)})

        task.refresh_from_db()
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        task = self._get_object(request, pk)
        self.check_object_permissions(request, task)

        try:
            TaskService.cancel_task(
                tenant_id=task.tenant_id,
                facility_id=task.facility_id,
                task_id=task.id,
            )
        except DjangoValidationError as e:
            raise DRFValidationError({"detail": str(e)})

        task.refresh_from_db()
        return Response(TaskSerializer(task).data, status=status.HTTP_200_OK)

    # ----------------------------
    # Backfill (admin-only via permission)
    # ----------------------------
    @action(detail=False, methods=["post"], url_path="backfill-done")
    def backfill_done(self, request):
        tenant_id, facility_id = self._require_scope(request)

        encounter_id = request.data.get("encounter_id")
        code = request.data.get("code")
        if not encounter_id or not code:
            raise DRFValidationError({"detail": "encounter_id and code are required."})

        updated = TaskService.backfill_mark_done(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            code=code,
        )
        return Response({"updated": updated}, status=status.HTTP_200_OK)
