# backend/hm_core/tasks/api/serializers.py
from __future__ import annotations

from rest_framework import serializers

from hm_core.tasks.models import Task


class TaskSerializer(serializers.ModelSerializer):
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "tenant_id",
            "facility_id",
            "encounter_id",
            "code",
            "title",
            "status",
            "assigned_to_id",
            "due_at",
            "completed_at",
            "is_overdue",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
