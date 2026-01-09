from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from django.db import transaction
from django.utils.timezone import now

from hm_core.rules.models import Rule


@dataclass(frozen=True)
class UpsertRuleResult:
    rule: Rule
    created: bool


class RuleService:
    """
    Rules write-model service.

    Why this exists:
    - keep writes out of selectors/engine
    - admin/seed scripts/tests can call one stable API
    - update/create behavior is deterministic and scope-safe

    Rule uniqueness:
      (tenant_id, facility_id, code)
    """

    @staticmethod
    @transaction.atomic
    def upsert_rule(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        code: str,
        description: str = "",
        is_active: bool = True,
        config: Optional[dict[str, Any]] = None,
    ) -> UpsertRuleResult:
        code = (code or "").strip()
        if not code:
            raise ValueError("Rule code is required.")

        cfg = dict(config or {})

        obj, created = Rule.objects.update_or_create(
            tenant_id=tenant_id,
            facility_id=facility_id,
            code=code,
            defaults={
                "description": description or "",
                "is_active": bool(is_active),
                "config": cfg,
                # ScopedModel typically has updated_at auto; but be safe if not.
                "updated_at": now(),
            },
        )
        return UpsertRuleResult(rule=obj, created=created)

    @staticmethod
    @transaction.atomic
    def set_rule_active(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        code: str,
        is_active: bool,
    ) -> int:
        """
        Returns number of rows updated (0 or 1).
        """
        code = (code or "").strip()
        if not code:
            raise ValueError("Rule code is required.")

        return Rule.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            code=code,
        ).update(is_active=bool(is_active), updated_at=now())

    # -----------------------------
    # Project standard defaults
    # -----------------------------
    @staticmethod
    def ensure_default_close_gate_rule(
        *,
        tenant_id: UUID,
        facility_id: UUID,
        required_tasks: Optional[list[str]] = None,
        required_docs: Optional[list[str]] = None,
        block_on_critical_unacked: bool = True,
        block_on_unverified_lab: bool = False,
        is_active: bool = True,
    ) -> UpsertRuleResult:
        """
        Ensures the canonical close-gate rule exists:
          code = "encounter.close_gate"

        This matches RuleEngine._load_close_gate_config().
        """
        cfg = {
            "required_tasks": required_tasks or ["record-vitals", "doctor-consult"],
            "required_docs": required_docs or ["VITALS", "ASSESSMENT", "PLAN"],
            "block_on_critical_unacked": bool(block_on_critical_unacked),
            "block_on_unverified_lab": bool(block_on_unverified_lab),
        }

        return RuleService.upsert_rule(
            tenant_id=tenant_id,
            facility_id=facility_id,
            code="encounter.close_gate",
            description="Encounter close completeness gate",
            is_active=is_active,
            config=cfg,
        )
