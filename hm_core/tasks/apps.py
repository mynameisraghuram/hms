# backend/hm_core/tasks/apps.py
from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hm_core.tasks"

    def ready(self):
        # Load signals (shim will import the canonical signals package)
        try:
            from hm_core.tasks import signals  # noqa: F401
        except Exception:
            pass
