# backend/hm_core/iam/apps.py
from django.apps import AppConfig


class IamConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hm_core.iam"
