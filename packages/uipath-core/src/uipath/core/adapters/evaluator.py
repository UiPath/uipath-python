"""Structural contract for the policy evaluator a framework plugin talks to.

Framework plugins call into a policy evaluator at each lifecycle hook.
Concrete evaluator implementations (the native runtime evaluator, a
Microsoft AGT bridge, a composite, …) live in packages outside
``uipath-core`` — plugins depend only on this structural protocol so
they can be swapped against any of them without code change.

``EvaluatorProtocol`` is a :class:`typing.Protocol` so any class whose
methods match the signatures below satisfies the contract without
inheritance.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from uipath.core.governance.models import AuditRecord


@runtime_checkable
class EvaluatorProtocol(Protocol):
    """Structural protocol a framework plugin expects from a policy evaluator.

    Every ``evaluate_*`` method returns an :class:`AuditRecord` — the
    per-hook audit envelope holding the per-rule
    :class:`RuleEvaluation` list, the final action, and the trace /
    agent metadata. Callers get a typed result; no downcasting is
    required.
    """

    def evaluate_before_agent(
        self,
        agent_input: str,
        agent_name: str,
        runtime_id: str,
        model_name: str = "",
        **kwargs: Any,
    ) -> AuditRecord:
        """Evaluate BEFORE_AGENT rules."""
        ...

    def evaluate_after_agent(
        self,
        agent_output: str,
        agent_name: str,
        runtime_id: str,
        **kwargs: Any,
    ) -> AuditRecord:
        """Evaluate AFTER_AGENT rules."""
        ...

    def evaluate_before_model(
        self,
        model_input: str,
        agent_name: str,
        runtime_id: str,
        messages: list[dict[str, Any]] | None = None,
        model_name: str = "",
        **kwargs: Any,
    ) -> AuditRecord:
        """Evaluate BEFORE_MODEL rules."""
        ...

    def evaluate_after_model(
        self,
        model_output: str,
        agent_name: str,
        runtime_id: str,
        **kwargs: Any,
    ) -> AuditRecord:
        """Evaluate AFTER_MODEL rules."""
        ...

    def evaluate_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        agent_name: str,
        runtime_id: str,
        session_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AuditRecord:
        """Evaluate TOOL_CALL rules."""
        ...

    def evaluate_after_tool(
        self,
        tool_name: str,
        tool_result: str,
        agent_name: str,
        runtime_id: str,
        **kwargs: Any,
    ) -> AuditRecord:
        """Evaluate AFTER_TOOL rules."""
        ...
