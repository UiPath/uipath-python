"""Shared governance contracts.

Two groups of types live here, both kept free of policy-input concepts
(``Rule``/``Check``/``Condition``) so adapter packages don't inherit
the native policy model:

- **Output types** (:class:`Action`, :class:`LifecycleHook`,
  :class:`RuleEvaluation`, :class:`AuditRecord`) — cross the adapter
  boundary at evaluation time: every evaluator implementation (native,
  AGT, composite, …) produces them, and every adapter consumes them.
- **Configuration value types** (:class:`EnforcementMode`) — describe
  governance configuration shared by core and its consumers. The
  per-policy runtime state that selects a mode lives outside this
  package; only the value type lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Action(str, Enum):
    """Actions that can be taken when a rule matches."""

    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"
    ESCALATE = "escalate"


class LifecycleHook(str, Enum):
    """Agent lifecycle hooks where rules can be evaluated."""

    BEFORE_AGENT = "before_agent"
    AFTER_AGENT = "after_agent"
    BEFORE_MODEL = "before_model"
    AFTER_MODEL = "after_model"
    TOOL_CALL = "tool_call"
    AFTER_TOOL = "after_tool"


class EnforcementMode(str, Enum):
    """Governance enforcement modes."""

    AUDIT = "audit"  # Evaluate and log; never block.
    ENFORCE = "enforce"  # Block on DENY rules.
    DISABLED = "disabled"  # Skip evaluation entirely.


@dataclass
class RuleEvaluation:
    """Result of evaluating a single rule."""

    rule_id: str
    rule_name: str
    matched: bool
    detail: str = ""
    pack_name: str = ""
    action: Action = Action.ALLOW
    description: str = ""
    check_results: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AuditRecord:
    """Complete audit record for a governance evaluation.

    ``trace_id`` is intentionally absent. Trace correlation is resolved
    by the concrete provider at request time (via OpenTelemetry's
    native span identity) — per-evaluation trace ids aren't part of
    the audit-record contract.
    """

    timestamp: datetime
    agent_name: str
    runtime_id: str
    hook: LifecycleHook
    evaluations: list[RuleEvaluation]
    final_action: Action
    metadata: dict[str, Any] = field(default_factory=dict)
    rules_matched: int = field(init=False)

    def __post_init__(self) -> None:
        """Derive rules_matched from the evaluations list."""
        self.rules_matched = sum(1 for e in self.evaluations if e.matched)
