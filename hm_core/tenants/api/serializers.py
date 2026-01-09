# backend/hm_core/tenants/api/serializers.py
from __future__ import annotations

from rest_framework import serializers

from hm_core.tenants.models import Tenant, TenantStatus


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "code",
            "status",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TenantCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    code = serializers.SlugField(max_length=64)
    status = serializers.ChoiceField(choices=TenantStatus.choices, required=False, default=TenantStatus.ACTIVE)
    metadata = serializers.JSONField(required=False, default=dict)


class TenantStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TenantStatus.choices)


class TenantMetadataUpdateSerializer(serializers.Serializer):
    metadata = serializers.JSONField()
