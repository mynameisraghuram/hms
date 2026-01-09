# backend/hm_core/clinical_docs/apps.py
from django.apps import AppConfig


class ClinicalDocsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hm_core.clinical_docs"

    def ready(self):
        # ensure signal receivers register
        try:
            from hm_core.clinical_docs import signals  # noqa: F401
        except Exception:
            pass
