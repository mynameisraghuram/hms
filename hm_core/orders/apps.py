# backend/hm_core/orders/apps.py
from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hm_core.orders"
