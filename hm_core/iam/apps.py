from django.apps import AppConfig


class IamConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hm_core.iam"

    def ready(self) -> None:
        # import here so app loading doesn’t break tooling
        from hm_core.iam import signals  # noqa: F401
        from hm_core.iam import openapi  # noqa: F401
