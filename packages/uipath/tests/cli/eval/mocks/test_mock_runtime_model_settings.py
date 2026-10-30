"""Tests for the model settings the legacy tool-simulation mocker is built with."""

from uipath.eval.mocks._mock_runtime import build_mocking_context
from uipath.eval.mocks._simulation_model import simulation_completion_kwargs
from uipath.eval.mocks._types import LLMMockingStrategy, SimulationConfig


def _legacy_config(**overrides: object) -> SimulationConfig:
    return SimulationConfig.model_validate(
        {
            "enabled": True,
            "instructions": "Simulate it",
            "toolsToSimulate": [{"name": "Get Records"}],
            **overrides,
        }
    )


def _strategy(context: object) -> LLMMockingStrategy:
    strategy = getattr(context, "strategy", None)
    assert isinstance(strategy, LLMMockingStrategy)
    return strategy


def test_agent_model_fallback_carries_agent_max_tokens():
    context = build_mocking_context(
        _legacy_config(), agent_model="gpt-4.1-2025-04-14", agent_max_tokens=16384
    )

    strategy = _strategy(context)
    assert strategy.model is not None
    assert strategy.model.model == "gpt-4.1-2025-04-14"
    assert strategy.model.max_tokens == 16384
    # The simulation call goes out at the agent's limit, not the 4096 default.
    assert simulation_completion_kwargs(strategy.model) == {
        "model": "gpt-4.1-2025-04-14",
        "max_tokens": 16384,
    }


def test_agent_model_fallback_without_max_tokens_omits_it():
    context = build_mocking_context(_legacy_config(), agent_model="gpt-4.1-2025-04-14")

    strategy = _strategy(context)
    assert strategy.model is not None
    assert "max_tokens" not in simulation_completion_kwargs(strategy.model)


def test_simulation_model_override_does_not_take_agent_max_tokens():
    # A different simulation model may have a lower output cap than the agent's.
    context = build_mocking_context(
        _legacy_config(model="claude-haiku-4-5"),
        agent_model="gpt-4.1-2025-04-14",
        agent_max_tokens=16384,
    )

    strategy = _strategy(context)
    assert strategy.model is not None
    assert strategy.model.model == "claude-haiku-4-5"
    assert strategy.model.max_tokens is None
