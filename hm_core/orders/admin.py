# backend/hm_core/orders/admin.py
from __future__ import annotations

from django.contrib import admin

from hm_core.orders.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("id", "service_code", "priority", "status", "created_at", "updated_at")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant_id",
        "facility_id",
        "encounter",
        "order_type",
        "priority",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = ("order_type", "priority", "status")
    search_fields = ("id", "encounter_id")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("encounter",)
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant_id",
        "facility_id",
        "order",
        "encounter",
        "service_code",
        "priority",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = ("priority", "status")
    search_fields = ("id", "order_id", "encounter_id", "service_code")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("order", "encounter")
