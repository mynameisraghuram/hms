# backend/hm_core/audit/api/serializers.py
from rest_framework import serializers
from hm_core.audit.models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    # Keep API field name "timestamp", but map it to real model field "occurred_at"
    timestamp = serializers.DateTimeField(source="occurred_at", read_only=True)

    # actor_user_id is already the correct attribute name exposed by Django for FK
    actor_user_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "tenant_id",
            "facility_id",
            "entity_type",
            "entity_id",
            "event_code",
            "actor_user_id",
            "timestamp",
            "metadata",
        ]
        read_only_fields = fields
