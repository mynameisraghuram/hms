# backend/hm_core/patients/api/serializers.py
from __future__ import annotations

from rest_framework import serializers

from hm_core.patients.models import Patient


class PatientCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    mrn = serializers.CharField(max_length=64)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    gender = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    date_of_birth = serializers.DateField(required=False, allow_null=True)


class PatientUpdateSerializer(serializers.Serializer):
    """
    Partial update contract (PATCH).
    """
    full_name = serializers.CharField(max_length=255, required=False)
    mrn = serializers.CharField(max_length=64, required=False)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    gender = serializers.CharField(max_length=32, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one field is required.")
        return attrs


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = [
            "id",
            "tenant_id",
            "facility_id",
            "full_name",
            "mrn",
            "phone",
            "email",
            "gender",
            "date_of_birth",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
