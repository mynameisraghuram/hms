# backend/hm_core/lab/api/serializers.py
from __future__ import annotations

from rest_framework import serializers

from hm_core.lab.models import LabSample, LabResult


class SampleReceiveSerializer(serializers.Serializer):
    order_item_id = serializers.UUIDField()
    barcode = serializers.CharField(required=False, allow_blank=True)


class LabSampleSerializer(serializers.ModelSerializer):
    order_item_id = serializers.UUIDField(source="order_item.id", read_only=True)

    class Meta:
        model = LabSample
        fields = ["id", "order_item_id", "barcode", "received_at"]


class LabResultCreateSerializer(serializers.Serializer):
    order_item_id = serializers.UUIDField()
    result_payload = serializers.JSONField()


class LabResultSerializer(serializers.ModelSerializer):
    order_item_id = serializers.UUIDField(source="order_item.id", read_only=True)

    class Meta:
        model = LabResult
        fields = [
            "id",
            "order_item_id",
            "version",
            "result_payload",
            "is_critical",
            "critical_reasons",
            "verified_at",
            "released_at",
        ]
