# backend/hm_core/facilities/api/serializers.py
from __future__ import annotations

from rest_framework import serializers

from hm_core.facilities.models import Facility, FacilityType


class FacilitySerializer(serializers.ModelSerializer):
    parent_facility_id = serializers.UUIDField(source="parent_facility.id", read_only=True)

    class Meta:
        model = Facility
        fields = [
            "id",
            "tenant_id",
            "name",
            "code",
            "facility_type",
            "parent_facility_id",
            "timezone",
            "phone",
            "email",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "pincode",
            "country",
            "registration_number",
            "gstin",
            "is_active",
            "deactivated_at",
            "deactivation_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant_id", "created_at", "updated_at"]


class FacilityCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    code = serializers.SlugField(max_length=64)
    facility_type = serializers.ChoiceField(choices=FacilityType.choices, required=False)
    parent_facility_id = serializers.UUIDField(required=False, allow_null=True)

    timezone = serializers.CharField(max_length=64, required=False, default="Asia/Kolkata")
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")

    address_line1 = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")
    state = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")
    pincode = serializers.CharField(max_length=16, required=False, allow_blank=True, default="")
    country = serializers.CharField(max_length=64, required=False, allow_blank=True, default="India")

    registration_number = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    gstin = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")


class FacilityUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False)
    code = serializers.SlugField(max_length=64, required=False)
    facility_type = serializers.ChoiceField(choices=FacilityType.choices, required=False)
    parent_facility_id = serializers.UUIDField(required=False, allow_null=True)

    timezone = serializers.CharField(max_length=64, required=False)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)

    address_line1 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=128, required=False, allow_blank=True)
    state = serializers.CharField(max_length=128, required=False, allow_blank=True)
    pincode = serializers.CharField(max_length=16, required=False, allow_blank=True)
    country = serializers.CharField(max_length=64, required=False, allow_blank=True)

    registration_number = serializers.CharField(max_length=64, required=False, allow_blank=True)
    gstin = serializers.CharField(max_length=32, required=False, allow_blank=True)

    is_active = serializers.BooleanField(required=False)
    deactivation_reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
