# backend/hm_core/rules/engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
from uuid import UUID

from rest_framework.exceptions import ValidationError

from hm_core.clinical_docs.models import EncounterDocument
from hm_core.tasks.models import Task, TaskStatus
from hm_core.rules.models import Rule

# Keep this import for hard blocker only (critical ack),
# so we don't break your existing EncounterRuleEngine logic there.
from hm_core.encounters.rules import EncounterRuleEngine


class GateFailed(Exception):
    def __init__(self, code: str, details: Dict[str, Any]):
        super().__init__(code)
        self.code = code
        self.details = details


@dataclass(frozen=True)
class GateResult:
    ok: bool
    code: str
    missing_tasks: list[str]
    missing_docs: list[str]
    reasons: list[dict]


@dataclass(frozen=True)
class CloseGateResult:
    can_close: bool
    ok: bool
    missing: dict  # {"docs_missing": [...], "tasks_open": [...], "DOCS": bool, "TASKS": bool, ...}


class RuleEngine:
    """
    ✅ Canonical RuleEngine.
    Import THIS everywhere:
        from hm_core.rules.engine import RuleEngine
    """

    # -----------------------
    # Hard blocker (close)
    # -----------------------
    @staticmethod
    def enforce_critical_ack_gate(*, tenant_id: UUID, facility_id: UUID, encounter_id: UUID) -> None:
        # Keep existing behavior (already passing tests)
        return EncounterRuleEngine.enforce_critical_ack_gate(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
        )

    # -----------------------
    # Advisory completeness (close-gate)
    # -----------------------
    @staticmethod
    def _load_close_gate_config(*, tenant_id: UUID, facility_id: UUID) -> tuple[list[str], list[str], dict]:
        """
        Source of truth:
        Rule(code="encounter.close_gate").config:
            {
              "required_tasks": [...],
              "required_docs": [...],

              # close-strict toggles (optional)
              "block_on_critical_unacked": true|false,
              "block_on_unverified_lab": true|false
            }

        Tests seed this rule and expect it to drive docs/tasks behavior.
        """
        rule = Rule.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            code="encounter.close_gate",
            is_active=True,
        ).first()

        config = (rule.config or {}) if rule else {}
        required_tasks = list(config.get("required_tasks") or ["record-vitals", "doctor-consult"])
        required_docs = list(config.get("required_docs") or ["VITALS", "ASSESSMENT", "PLAN"])
        return required_tasks, required_docs, config

    @staticmethod
    def check_encounter_close_gate(*, tenant_id: UUID, facility_id: UUID, encounter_id: UUID) -> CloseGateResult:
        """
        Advisory gate used by /close-gate/.
        Uses Rule config (required_docs/required_tasks) and is resilient to duplicate tasks:
        DONE "wins" over OPEN/IN_PROGRESS if any DONE exists for the same code.
        """
        required_tasks, required_docs, _config = RuleEngine._load_close_gate_config(
            tenant_id=tenant_id,
            facility_id=facility_id,
        )

        # ----- docs -----
        existing_docs = set(
            EncounterDocument.objects.filter(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=encounter_id,
                kind__in=required_docs,
            ).values_list("kind", flat=True)
        )
        docs_missing = [k for k in required_docs if k not in existing_docs]

        # ----- tasks -----
        # rank: higher is better (DONE wins)
        rank = {
            TaskStatus.DONE: 3,
            TaskStatus.CANCELLED: 2,   # treat as "not blocking" (optional)
            TaskStatus.IN_PROGRESS: 1,
            TaskStatus.OPEN: 0,
        }

        rows = Task.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
            code__in=required_tasks,
        ).values_list("code", "status")

        best_rank_by_code: dict[str, int] = {}
        best_status_by_code: dict[str, str] = {}

        for code, st in rows:
            r = rank.get(st, -1)
            if code not in best_rank_by_code or r > best_rank_by_code[code]:
                best_rank_by_code[code] = r
                best_status_by_code[code] = st

        tasks_open: list[str] = []
        for code in required_tasks:
            st = best_status_by_code.get(code)
            if st is None:
                # missing task record counts as "open/missing" for gate purposes
                tasks_open.append(code)
            elif st != TaskStatus.DONE:
                # not DONE counts as open for gate purposes
                tasks_open.append(code)

        missing = {
            "docs_missing": docs_missing,
            "tasks_open": tasks_open,
            "DOCS": bool(docs_missing),
            "TASKS": bool(tasks_open),
        }

        ok = (not docs_missing) and (not tasks_open)
        return CloseGateResult(can_close=ok, ok=ok, missing=missing)

    # -----------------------
    # Optional strict safety: unverified lab results
    # -----------------------
    @staticmethod
    def _has_unverified_lab_results(*, tenant_id: UUID, facility_id: UUID, encounter_id: UUID) -> bool:
        """
        Returns True if there exist lab results linked to this encounter that are not verified.
        Local imports to avoid module import coupling if lab isn't fully stable yet.

        ASSUMPTIONS (we will confirm with you):
        - LabResult has field: verified_at
        - LabResult has FK: order_item
        - OrderItem has FK/field: encounter_id
        """
        from hm_core.lab.models import LabResult  # local import
        return LabResult.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            order_item__encounter_id=encounter_id,
            verified_at__isnull=True,
        ).exists()

    # -----------------------
    # Strict completeness enforcement (close-strict)
    # -----------------------
    @staticmethod
    def enforce_encounter_close_gate(*, tenant_id: UUID, facility_id: UUID, encounter_id: UUID) -> None:
        """
        Strict completeness enforcement.
        Raise ValidationError when close-gate is not satisfied.

        STRICT includes:
        - docs/tasks completeness (rule-config driven)
        - critical-ack hard safety blocker (if enabled)
        - optional unverified-lab blocker (if enabled)
        """
        required_tasks, required_docs, _config = RuleEngine._load_close_gate_config(
            tenant_id=tenant_id,
            facility_id=facility_id,
        )

        # existing completeness evaluation
        r = RuleEngine.check_encounter_close_gate(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
        )

        # load rule again to read extra flags (backward compatible)
        rule = Rule.objects.filter(
            tenant_id=tenant_id,
            facility_id=facility_id,
            code="encounter.close_gate",
            is_active=True,
        ).first()
        config = (rule.config or {}) if rule else {}

        block_on_critical_unacked = bool(config.get("block_on_critical_unacked", True))
        block_on_unverified_lab = bool(config.get("block_on_unverified_lab", False))

        missing = dict(r.missing)

        # ---- critical ack blocker (strict) ----
        if block_on_critical_unacked:
            try:
                RuleEngine.enforce_critical_ack_gate(
                    tenant_id=tenant_id,
                    facility_id=facility_id,
                    encounter_id=encounter_id,
                )
            except ValidationError:
                missing["CRITICAL_ACK"] = True

        # ---- optional: unverified lab results blocker (strict) ----
        if block_on_unverified_lab:
            from hm_core.lab.models import LabResult

            has_unverified = LabResult.objects.filter(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=encounter_id,
                verified_at__isnull=True,
            ).exists()

            if has_unverified:
                missing["UNVERIFIED_LAB_RESULTS"] = True

        ok = bool(r.ok) and (not missing.get("CRITICAL_ACK")) and (not missing.get("UNVERIFIED_LAB_RESULTS"))
        if not ok:
            raise ValidationError(
                {
                    "detail": "Encounter close blocked by close-gate rules.",
                    "ok": False,
                    "can_close": False,
                    "missing": missing,
                }
            )

    # -----------------------
    # Backward-compatible API
    # -----------------------
    @staticmethod
    def evaluate_encounter_close_gate(*, tenant_id: UUID, facility_id: UUID, encounter_id: UUID) -> GateResult:
        """
        Compatibility wrapper that returns the older GateResult shape:
          - missing_docs: list[str]
          - missing_tasks: list[str]
          - reasons: list[dict]

        Includes safety reasons as advisory markers.
        """
        r = RuleEngine.check_encounter_close_gate(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
        )

        _required_tasks, _required_docs, config = RuleEngine._load_close_gate_config(
            tenant_id=tenant_id,
            facility_id=facility_id,
        )
        block_on_critical_unacked = bool(config.get("block_on_critical_unacked", True))
        block_on_unverified_lab = bool(config.get("block_on_unverified_lab", False))

        missing_docs = list(r.missing.get("docs_missing", []))
        missing_tasks = list(r.missing.get("tasks_open", []))

        reasons: list[dict] = []
        for k in missing_docs:
            reasons.append({"type": "DOC_MISSING", "kind": k})
        for c in missing_tasks:
            reasons.append({"type": "TASK_NOT_DONE", "code": c})

        if block_on_critical_unacked:
            try:
                RuleEngine.enforce_critical_ack_gate(
                    tenant_id=tenant_id,
                    facility_id=facility_id,
                    encounter_id=encounter_id,
                )
            except ValidationError:
                reasons.append({"type": "SAFETY_BLOCK", "code": "CRITICAL_ACK"})

        if block_on_unverified_lab:
            if RuleEngine._has_unverified_lab_results(
                tenant_id=tenant_id,
                facility_id=facility_id,
                encounter_id=encounter_id,
            ):
                reasons.append({"type": "SAFETY_BLOCK", "code": "UNVERIFIED_LAB_RESULTS"})

        ok = bool(r.ok) and not any(rr.get("type") == "SAFETY_BLOCK" for rr in reasons)
        return GateResult(
            ok=ok,
            code="OK" if ok else "BLOCKED",
            missing_tasks=missing_tasks,
            missing_docs=missing_docs,
            reasons=reasons,
        )

    @staticmethod
    def enforce_close_gate(*, tenant_id: UUID, facility_id: UUID, encounter_id: UUID) -> None:
        """
        Another compatibility helper: raise ValidationError using stable payload.
        """
        return RuleEngine.enforce_encounter_close_gate(
            tenant_id=tenant_id,
            facility_id=facility_id,
            encounter_id=encounter_id,
        )
