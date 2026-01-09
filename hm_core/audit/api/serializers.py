#backend/hm_core/audit/api/serializers.py
from rest_framework import serializers
from hm_core.audit.models import AuditEvent

class AuditEventSerializer(serializers.ModelSerializer):
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

