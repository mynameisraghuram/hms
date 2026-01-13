# backend/hm_core/charges/tests/test_charge_item_model.py
import pytest
from django.db import IntegrityError

from hm_core.charges.models import ChargeItem

pytestmark = pytest.mark.django_db


def test_charge_item_unique_per_scope(tenant, facility):
    ChargeItem.objects.create(
        tenant_id=tenant.id,
        facility_id=facility.id,
        code="cbc",
        name="CBC",
        default_price="250.00",
        tax_percent="18.00",
        is_active=True,
    )

    # UniqueConstraint on (tenant_id, facility_id, code)
    with pytest.raises(IntegrityError):
        ChargeItem.objects.create(
            tenant_id=tenant.id,
            facility_id=facility.id,
            code="cbc",
            name="CBC Duplicate",
            default_price="300.00",
            tax_percent="18.00",
            is_active=True,
        )
