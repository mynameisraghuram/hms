# backend/hm_core/orders/api/serializers.py
from __future__ import annotations

from rest_framework import serializers

from hm_core.orders.models import Order, OrderItem, OrderPriority, OrderType


class OrderItemCreateSerializer(serializers.Serializer):
    service_code = serializers.SlugField(max_length=64)
    priority = serializers.ChoiceField(choices=OrderPriority.choices, required=False)


class OrderCreateSerializer(serializers.Serializer):
    encounter_id = serializers.UUIDField()
    order_type = serializers.ChoiceField(choices=OrderType.choices)
    priority = serializers.ChoiceField(
        choices=OrderPriority.choices,
        required=False,
        default=OrderPriority.ROUTINE,
    )
    items = OrderItemCreateSerializer(many=True)


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "service_code", "priority", "status"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["id", "encounter", "order_type", "priority", "status", "items"]
