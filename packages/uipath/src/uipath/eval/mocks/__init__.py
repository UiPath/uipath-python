"""Mock interface."""

from ._mock_context import is_tool_simulated
from ._mock_runtime import (
    UiPathMockRuntime,
    build_mocking_context,
    build_mocking_context_from_dict,
)
from ._types import (
    ComponentSimulationConfig,
    ExampleCall,
    MockingContext,
    RuleOperator,
    SimulationAnswer,
    SimulationAnswerType,
    SimulationBehavior,
    SimulationCondition,
    SimulationConfig,
    SimulationStrategy,
)
from .mockable import mockable

__all__ = [
    "ComponentSimulationConfig",
    "ExampleCall",
    "MockingContext",
    "RuleOperator",
    "SimulationAnswer",
    "SimulationAnswerType",
    "SimulationBehavior",
    "SimulationCondition",
    "SimulationConfig",
    "SimulationStrategy",
    "UiPathMockRuntime",
    "build_mocking_context",
    "build_mocking_context_from_dict",
    "is_tool_simulated",
    "mockable",
]
