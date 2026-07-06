"""Tests for EvaluatorProtocol.

The protocol is a structural type. These tests verify two things:

1. A class whose method shapes match the protocol passes ``isinstance``
   against the ``runtime_checkable`` Protocol.
2. Subclassing the Protocol and calling ``super().<method>`` actually
   executes the stub bodies — this both documents that the stubs are
   safely callable (they return ``None``) and brings the contract module
   to full line coverage.
"""

from __future__ import annotations

from typing import Any

from uipath.core.adapters import EvaluatorProtocol


class _MissingMethodEvaluator:
    """Only implements one method — fails the structural check."""

    def evaluate_before_agent(self, *args: Any, **kwargs: Any) -> Any:
        return None


class _CompleteEvaluator:
    """All six methods present with the expected names — passes ``isinstance``."""

    def evaluate_before_agent(self, *args: Any, **kwargs: Any) -> Any:
        return "before-agent"

    def evaluate_after_agent(self, *args: Any, **kwargs: Any) -> Any:
        return "after-agent"

    def evaluate_before_model(self, *args: Any, **kwargs: Any) -> Any:
        return "before-model"

    def evaluate_after_model(self, *args: Any, **kwargs: Any) -> Any:
        return "after-model"

    def evaluate_tool_call(self, *args: Any, **kwargs: Any) -> Any:
        return "tool-call"

    def evaluate_after_tool(self, *args: Any, **kwargs: Any) -> Any:
        return "after-tool"


class _ProtocolSubclass(EvaluatorProtocol):
    """Subclass that delegates to ``super()`` — exercises the stub bodies.

    Each override calls ``super().<method>(...)`` so the ``...`` body of
    the Protocol method actually executes (returns ``None``).
    """

    def evaluate_before_agent(self, *args: Any, **kwargs: Any) -> Any:
        return super().evaluate_before_agent(*args, **kwargs)  # type: ignore[safe-super]

    def evaluate_after_agent(self, *args: Any, **kwargs: Any) -> Any:
        return super().evaluate_after_agent(*args, **kwargs)  # type: ignore[safe-super]

    def evaluate_before_model(self, *args: Any, **kwargs: Any) -> Any:
        return super().evaluate_before_model(*args, **kwargs)  # type: ignore[safe-super]

    def evaluate_after_model(self, *args: Any, **kwargs: Any) -> Any:
        return super().evaluate_after_model(*args, **kwargs)  # type: ignore[safe-super]

    def evaluate_tool_call(self, *args: Any, **kwargs: Any) -> Any:
        return super().evaluate_tool_call(*args, **kwargs)  # type: ignore[safe-super]

    def evaluate_after_tool(self, *args: Any, **kwargs: Any) -> Any:
        return super().evaluate_after_tool(*args, **kwargs)  # type: ignore[safe-super]


# ---------------------------------------------------------------------------
# Structural conformance
# ---------------------------------------------------------------------------


def test_complete_evaluator_is_recognized_by_runtime_check():
    """A class with all six methods passes ``isinstance`` against the protocol."""
    assert isinstance(_CompleteEvaluator(), EvaluatorProtocol)


def test_partial_evaluator_is_rejected_by_runtime_check():
    """A class missing methods does NOT pass the structural check."""
    assert not isinstance(_MissingMethodEvaluator(), EvaluatorProtocol)


# ---------------------------------------------------------------------------
# Stub-body execution (line coverage for the ``...`` placeholders)
# ---------------------------------------------------------------------------


def test_protocol_subclass_methods_execute_stub_bodies():
    """Calling each method via ``super()`` executes the stub body and returns None."""
    e = _ProtocolSubclass()

    assert e.evaluate_before_agent("input", "agent", "rt") is None
    assert e.evaluate_after_agent("output", "agent", "rt") is None
    assert e.evaluate_before_model("input", "agent", "rt") is None
    assert e.evaluate_after_model("output", "agent", "rt") is None
    assert e.evaluate_tool_call("tool", {"arg": 1}, "agent", "rt") is None
    assert e.evaluate_after_tool("tool", "result", "agent", "rt") is None
