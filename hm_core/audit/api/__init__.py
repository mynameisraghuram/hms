# backend/hm_core/audit/api/serializers.py
from __future__ import annotations

from rest_framework import serializers

from hm_core.audit.models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actor_user_id = serializers.IntegerField(source="actor_user.id", read_only=True, allow_null=True)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "tenant_id",
            "facility_id",
            "event_code",
            "entity_type",
            "entity_id",
            "actor_user_id",
            "occurred_at",
            "metadata",
        ]
        read_only_fields = fields
