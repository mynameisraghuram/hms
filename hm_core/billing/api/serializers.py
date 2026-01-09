# backend/hm_core/billing/api/serializers.py
from __future__ import annotations

from rest_framework import serializers

from hm_core.billing.models import BillableEvent


class BillableEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillableEvent
        fields = [
            "id",
            "tenant_id",
            "facility_id",
            "encounter",
            "event_type",
            "chargeable_code",
            "quantity",
            "source_order_item",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
