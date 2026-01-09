# backend/hm_core/rules/models.py
from django.db import models
from hm_core.common.models import ScopedModel


class Rule(ScopedModel):
    """
    Minimal rule definition for Phase 0:
    - code identifies a gate/check (e.g., "encounter.close_gate")
    - config stores required tasks/docs etc (JSON)
    """
    code = models.CharField(max_length=128, db_index=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    config = models.JSONField(default=dict)

    class Meta:
        db_table = "rules_rule"
        constraints = [
            models.UniqueConstraint(fields=["tenant_id", "facility_id", "code"], name="uq_rule_scope_code"),
        ]
        indexes = [
            models.Index(fields=["tenant_id", "facility_id", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.code
