# backend/hm_core/encounters/serializers_events.py
from rest_framework import serializers
from hm_core.encounters.models import EncounterEvent


class EncounterEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = EncounterEvent
        fields = [
            "id",
            "type",
            "code",
            "title",
            "timestamp",
            "meta",
            "tenant_id",
            "facility_id",
            "encounter_id",
            "event_key",
        ]
