# backend/hm_core/encounters/serializers.py

from hm_core.clinical_docs.models import EncounterDocument
from rest_framework import serializers
from hm_core.encounters.models import Encounter


class EncounterCreateSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
    attending_doctor_id = serializers.IntegerField(required=False, allow_null=True)
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)


class EncounterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Encounter
        fields = [
            "id",
            "tenant_id",
            "facility_id",
            "patient_id",
            "status",
            "scheduled_at",
            "checked_in_at",
            "consult_started_at",
            "closed_at",
            "reason",
            "attending_doctor_id",
            "created_by_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class VitalsInputSerializer(serializers.Serializer):
    # Simple, safe validation (Phase 0.6)
    temperature_c = serializers.FloatField(required=False, min_value=25, max_value=45)
    pulse_bpm = serializers.IntegerField(required=False, min_value=20, max_value=250)
    resp_rate = serializers.IntegerField(required=False, min_value=5, max_value=80)

    bp_systolic = serializers.IntegerField(required=False, min_value=50, max_value=300)
    bp_diastolic = serializers.IntegerField(required=False, min_value=30, max_value=200)

    spo2 = serializers.IntegerField(required=False, min_value=0, max_value=100)
    weight_kg = serializers.FloatField(required=False, min_value=0, max_value=500)
    height_cm = serializers.FloatField(required=False, min_value=0, max_value=300)

    note = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs):
        # If BP is provided, require both systolic and diastolic
        sys = attrs.get("bp_systolic")
        dia = attrs.get("bp_diastolic")
        if (sys is None) ^ (dia is None):
            raise serializers.ValidationError("Provide both bp_systolic and bp_diastolic together.")
        if not attrs:
            raise serializers.ValidationError("At least one vitals field is required.")
        return attrs


class AssessmentInputSerializer(serializers.Serializer):
    chief_complaint = serializers.CharField(required=False, max_length=500)
    history = serializers.CharField(required=False, allow_blank=True)
    diagnosis = serializers.CharField(required=False, max_length=500)
    note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Assessment content cannot be empty.")
        return attrs


class PlanInputSerializer(serializers.Serializer):
    medications = serializers.ListField(
        required=False,
        child=serializers.DictField(),
    )
    investigations = serializers.ListField(
        required=False,
        child=serializers.CharField(),
    )
    advice = serializers.CharField(required=False, allow_blank=True)
    follow_up = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Plan content cannot be empty.")
        return attrs


class EncounterDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EncounterDocument
        fields = "__all__"
