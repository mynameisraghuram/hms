#backend/hm_core/charges/models.py
from __future__ import annotations

from decimal import Decimal

from django.db import models

from hm_core.common.models import ScopedModel


class ChargeItem(ScopedModel):
    """
    Charge Master / Pricing catalog.
    One record per tenant+facility+code.
    """
    code = models.SlugField(max_length=64)  # matches BillableEvent.chargeable_code
    name = models.CharField(max_length=255)

    department = models.CharField(max_length=64, blank=True)

    default_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))  # e.g. 18.00

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "charges_charge_item"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "facility_id", "code"],
                name="uq_charge_item_scope_code",
            )
        ]
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "code"]),
            models.Index(fields=["tenant_id", "facility_id", "is_active"]),
        ]
