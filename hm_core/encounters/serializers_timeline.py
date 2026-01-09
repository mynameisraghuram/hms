# backend/hm_core/encounters/serializers_timeline.py
from rest_framework import serializers


class EncounterTimelineEventSerializer(serializers.Serializer):
    type = serializers.CharField()
    at = serializers.DateTimeField(required=False, allow_null=True)

    # optional payload fields (we keep it flexible)
    code = serializers.CharField(required=False, allow_null=True)
    title = serializers.CharField(required=False, allow_null=True)
    status = serializers.CharField(required=False, allow_null=True)

    kind = serializers.CharField(required=False, allow_null=True)
    document_id = serializers.CharField(required=False, allow_null=True)

    task_id = serializers.CharField(required=False, allow_null=True)


class EncounterTimelineSerializer(serializers.Serializer):
    encounter = serializers.DictField()
    events = EncounterTimelineEventSerializer(many=True)
