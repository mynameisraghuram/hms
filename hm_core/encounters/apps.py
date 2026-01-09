# backend/hm_core/encounters/apps.py
# hm_core/encounters/apps.py
from django.apps import AppConfig


class EncountersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hm_core.encounters"

    def ready(self):
        # Import the signals package; __init__.py will import submodules
        import hm_core.encounters.signals  # noqa: F401
