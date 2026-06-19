"""Tests for BaseAdapter defaults and GovernedAgentBase proxy behavior."""

from __future__ import annotations

from typing import Any

import pytest

from uipath.core.adapters import BaseAdapter, EvaluatorProtocol
from uipath.core.adapters.base import GovernedAgentBase


class _StubEvaluator:
    """No-op evaluator that structurally matches EvaluatorProtocol."""

    def evaluate_before_agent(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def evaluate_after_agent(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def evaluate_before_model(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def evaluate_after_model(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def evaluate_tool_call(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def evaluate_after_tool(self, *args: Any, **kwargs: Any) -> Any:
        return None


class _MinimalAdapter(BaseAdapter):
    """Concrete adapter that does NOT override ``name`` — exercises the default."""

    def can_handle(self, agent: Any) -> bool:
        return True

    def attach(
        self,
        agent: Any,
        agent_id: str,
        session_id: str,
        evaluator: EvaluatorProtocol,
    ) -> Any:
        return agent


class _Agent:
    """Simple stand-in for a framework agent with one attribute and one method."""

    foo = "bar"

    def greet(self) -> str:
        return "hello"


# ---------------------------------------------------------------------------
# BaseAdapter defaults
# ---------------------------------------------------------------------------


def test_default_name_is_class_name():
    """The default ``name`` property returns the class name."""
    assert _MinimalAdapter().name == "_MinimalAdapter"


def test_detach_returns_unwrapped_when_present():
    """``detach`` honours the ``unwrapped`` contract on a governed proxy."""
    adapter = _MinimalAdapter()
    original = object()

    class _Proxy:
        unwrapped = original

    assert adapter.detach(_Proxy()) is original


def test_detach_returns_input_when_no_unwrapped_attribute():
    """For non-proxy adapters, ``detach`` returns the input unchanged."""
    adapter = _MinimalAdapter()
    raw = object()
    assert adapter.detach(raw) is raw


def test_generate_trace_id_returns_unique_uuid_string():
    """``_generate_trace_id`` returns a string UUID; consecutive calls differ."""
    adapter = _MinimalAdapter()
    a = adapter._generate_trace_id()
    b = adapter._generate_trace_id()
    assert isinstance(a, str)
    assert a != b
    assert len(a) == 36  # canonical UUID4 form: 32 hex + 4 dashes


# ---------------------------------------------------------------------------
# GovernedAgentBase proxy
# ---------------------------------------------------------------------------


def test_governed_agent_base_stores_metadata_and_generates_trace_id():
    """Constructor wires every governance field and pulls a trace id from the adapter."""
    agent = _Agent()
    adapter = _MinimalAdapter()
    evaluator = _StubEvaluator()

    governed = GovernedAgentBase(
        agent=agent,
        adapter=adapter,
        agent_id="agent-123",
        session_id="session-abc",
        evaluator=evaluator,
    )

    assert governed._agent is agent
    assert governed._adapter is adapter
    assert governed._agent_id == "agent-123"
    assert governed._session_id == "session-abc"
    assert governed._evaluator is evaluator
    assert isinstance(governed._trace_id, str)
    assert len(governed._trace_id) == 36


def test_governed_agent_base_unwrapped_returns_original_agent():
    agent = _Agent()
    governed = GovernedAgentBase(
        agent=agent,
        adapter=_MinimalAdapter(),
        agent_id="a",
        session_id="s",
        evaluator=_StubEvaluator(),
    )
    assert governed.unwrapped is agent


def test_governed_agent_base_forwards_attribute_access_to_agent():
    """Unknown attributes fall through to the wrapped agent via __getattr__."""
    governed = GovernedAgentBase(
        agent=_Agent(),
        adapter=_MinimalAdapter(),
        agent_id="a",
        session_id="s",
        evaluator=_StubEvaluator(),
    )

    assert governed.foo == "bar"
    assert governed.greet() == "hello"


def test_governed_agent_base_attribute_miss_raises_attribute_error():
    """If the wrapped agent also lacks the attribute, AttributeError surfaces."""
    governed = GovernedAgentBase(
        agent=_Agent(),
        adapter=_MinimalAdapter(),
        agent_id="a",
        session_id="s",
        evaluator=_StubEvaluator(),
    )

    with pytest.raises(AttributeError):
        _ = governed.does_not_exist
