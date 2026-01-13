# backend/hm_core/charges/services.py
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import UUID

from rest_framework.exceptions import ValidationError

from hm_core.charges.models import ChargeItem


class ChargeItemService:
    @staticmethod
    def _to_decimal(value, field_name: str) -> Decimal:
        """
        Accepts Decimal / str / int / float and converts to Decimal safely.
        Raises ValidationError for invalid values.
        """
        if isinstance(value, Decimal):
            return value
        try:
            # str() handles int/float/str uniformly
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError({field_name: "Invalid decimal value."})

    @staticmethod
    def upsert(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        code: str,
        name: str,
        default_price,
        tax_percent=Decimal("0.00"),
        department: str = "",
        is_active: bool = True,
    ) -> ChargeItem:
        default_price = ChargeItemService._to_decimal(default_price, "default_price").quantize(Decimal("0.01"))
        tax_percent = ChargeItemService._to_decimal(tax_percent, "tax_percent").quantize(Decimal("0.01"))

        if default_price < Decimal("0.00"):
            raise ValidationError({"default_price": "Must be >= 0"})
        if tax_percent < Decimal("0.00"):
            raise ValidationError({"tax_percent": "Must be >= 0"})

        obj, _ = ChargeItem.objects.update_or_create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            code=code,
            defaults={
                "name": name,
                "default_price": default_price,
                "tax_percent": tax_percent,
                "department": department or "",
                "is_active": is_active,
            },
        )
        return obj
