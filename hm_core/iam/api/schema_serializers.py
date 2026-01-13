# backend/hm_core/iam/api/schema_serializers.py
from __future__ import annotations

from rest_framework import serializers


class LoginRequestSerializer(serializers.Serializer):
    # supports either username or email depending on your User model
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    password = serializers.CharField()


class LoginResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class RefreshResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class LogoutResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class MeUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField(allow_null=True, required=False)
    email = serializers.EmailField(allow_null=True, required=False)
    is_superuser = serializers.BooleanField()


class ActiveScopeSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField()
    facility_id = serializers.UUIDField()


class MeResponseSerializer(serializers.Serializer):
    user = MeUserSerializer()
    memberships = serializers.ListField(child=serializers.DictField())
    active_scope = ActiveScopeSerializer(allow_null=True, required=False)


class ScopeSwitchRequestSerializer(serializers.Serializer):
    tenant_id = serializers.UUIDField()
    facility_id = serializers.UUIDField()


class ScopeSwitchResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    active_scope = ActiveScopeSerializer()
