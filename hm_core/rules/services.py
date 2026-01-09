# backend/hm_core/rules/services.py
from __future__ import annotations

"""
Compatibility shim.

✅ Canonical import path:
    from hm_core.rules.engine import RuleEngine

This module re-exports symbols so older imports keep working:
    from hm_core.rules.services import RuleEngine
"""

from hm_core.rules.engine import (  # noqa: F401
    RuleEngine,
    GateFailed,
    GateResult,
    CloseGateResult,
)

__all__ = [
    "RuleEngine",
    "GateFailed",
    "GateResult",
    "CloseGateResult",
]
