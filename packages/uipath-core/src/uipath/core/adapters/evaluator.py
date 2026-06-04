"""Structural contract for the policy evaluator an adapter talks to.

Framework adapters call into a policy evaluator at each lifecycle hook.
Concrete evaluator implementations (the native runtime evaluator, a
Microsoft AGT bridge, a composite, …) live in packages outside
``uipath-core`` — adapters depend only on this structural protocol so
they can be swapped against any of them without code change.

``EvaluatorProtocol`` is a :class:`typing.Protocol` so any class whose
methods match the signatures below satisfies the contract without
inheritance.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EvaluatorProtocol(Protocol):
    """Structural protocol an adapter expects from a policy evaluator.

    Return types are intentionally :class:`typing.Any`: the concrete
    audit record shape lives in the plugin package that owns the
    evaluator and the policy model. Adapters in that package cast the
    return value back to the concrete type they know.
    """

    def evaluate_before_agent(
        self,
        agent_input: str,
        agent_name: str,
        runtime_id: str,
        trace_id: str,
        model_name: str = "",
        **kwargs: Any,
    ) -> Any:
        """Evaluate BEFORE_AGENT rules."""
        ...

    def evaluate_after_agent(
        self,
        agent_output: str,
        agent_name: str,
        runtime_id: str,
        trace_id: str,
        **kwargs: Any,
    ) -> Any:
        """Evaluate AFTER_AGENT rules."""
        ...

    def evaluate_before_model(
        self,
        model_input: str,
        agent_name: str,
        runtime_id: str,
        trace_id: str,
        messages: list[dict[str, Any]] | None = None,
        model_name: str = "",
        **kwargs: Any,
    ) -> Any:
        """Evaluate BEFORE_MODEL rules."""
        ...

    def evaluate_after_model(
        self,
        model_output: str,
        agent_name: str,
        runtime_id: str,
        trace_id: str,
        **kwargs: Any,
    ) -> Any:
        """Evaluate AFTER_MODEL rules."""
        ...

    def evaluate_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        agent_name: str,
        runtime_id: str,
        trace_id: str,
        session_state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Evaluate TOOL_CALL rules."""
        ...

    def evaluate_after_tool(
        self,
        tool_name: str,
        tool_result: str,
        agent_name: str,
        runtime_id: str,
        trace_id: str,
        **kwargs: Any,
    ) -> Any:
        """Evaluate AFTER_TOOL rules."""
        ...
