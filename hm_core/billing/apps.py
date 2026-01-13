# backend/hm_core/billing/apps.py
from __future__ import annotations

from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hm_core.billing"

    def ready(self) -> None:
        from django.db.models.signals import post_save

        from hm_core.billing.models import BillableEvent
        from hm_core.billing.signals.billable_event_to_invoice import (
            auto_attach_billable_event_to_invoice,
        )

        post_save.connect(
            auto_attach_billable_event_to_invoice,
            sender=BillableEvent,
            dispatch_uid="billing.auto_attach_billable_event_to_invoice",
        )
