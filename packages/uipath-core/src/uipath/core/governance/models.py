"""Shared governance output types.

These dataclasses cross the adapter boundary — every evaluator
implementation (native, AGT, composite, …) produces them, and every
adapter consumes them. They are kept free of policy-input concepts
(``Rule``/``Check``/``Condition``) so the adapter packages don't
inherit the native policy model.
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
    """Complete audit record for a governance evaluation."""

    timestamp: datetime
    agent_name: str
    runtime_id: str
    trace_id: str
    hook: LifecycleHook
    evaluations: list[RuleEvaluation]
    final_action: Action
    metadata: dict[str, Any] = field(default_factory=dict)
    rules_matched: int = field(init=False)

    def __post_init__(self) -> None:
        """Derive rules_matched from the evaluations list."""
        self.rules_matched = sum(1 for e in self.evaluations if e.matched)
