"""Mocking types for evaluation and simulation."""

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class MockingStrategyType(str, Enum):
    """Supported mocking strategy types."""

    LLM = "llm"
    MOCKITO = "mockito"
    UNKNOWN = "unknown"


class BaseMockingStrategy(BaseModel):
    """Base class for mocking strategies."""

    pass


class ToolSimulation(BaseModel):
    """A tool to be simulated during evaluation."""

    name: str = Field(..., alias="name")


class ModelSettings(BaseModel):
    """Model generation parameters for LLM-based mocking."""

    model: str = Field(..., alias="model")
    temperature: float | str | None = Field(default=None, alias="temperature")
    top_p: float | None = Field(default=None, alias="topP")
    top_k: int | None = Field(default=None, alias="topK")
    frequency_penalty: float | None = Field(default=None, alias="frequencyPenalty")
    presence_penalty: float | None = Field(default=None, alias="presencePenalty")
    max_tokens: int | None = Field(default=None, alias="maxTokens")


class LLMMockingStrategy(BaseMockingStrategy):
    """Mocking strategy that uses an LLM to generate simulated tool responses."""

    type: Literal[MockingStrategyType.LLM] = MockingStrategyType.LLM
    prompt: str = Field(..., alias="prompt")
    tools_to_simulate: list[ToolSimulation] = Field(..., alias="toolsToSimulate")
    model: ModelSettings | None = Field(None, alias="model")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class InputMockingStrategy(BaseModel):
    """Strategy for generating mocked inputs via LLM."""

    prompt: str = Field(..., alias="prompt")
    model: ModelSettings | None = Field(None, alias="model")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class MockingArgument(BaseModel):
    """Arguments matcher for mockito-style mocking."""

    args: list[Any] = Field(default_factory=lambda: [], alias="args")
    kwargs: dict[str, Any] = Field(default_factory=lambda: {}, alias="kwargs")


class MockingAnswerType(str, Enum):
    """Type of answer a mock should produce."""

    RETURN = "return"
    RAISE = "raise"


class MockingAnswer(BaseModel):
    """A mock answer definition (return value or exception)."""

    type: MockingAnswerType
    value: Any = Field(..., alias="value")


class MockingBehavior(BaseModel):
    """Defines how a mocked function should behave."""

    function: str = Field(..., alias="function")
    arguments: MockingArgument | None = Field(default=None, alias="arguments")
    then: list[MockingAnswer] = Field(..., alias="then")


class MockitoMockingStrategy(BaseMockingStrategy):
    """Mocking strategy using mockito-style behavior definitions."""

    type: Literal[MockingStrategyType.MOCKITO] = MockingStrategyType.MOCKITO
    behaviors: list[MockingBehavior] = Field(..., alias="config")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


KnownMockingStrategy = Annotated[
    Union[LLMMockingStrategy, MockitoMockingStrategy],
    Field(discriminator="type"),
]


class UnknownMockingStrategy(BaseMockingStrategy):
    """Fallback for unrecognized mocking strategy types."""

    type: str = Field(..., alias="type")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


MockingStrategy = Union[KnownMockingStrategy, UnknownMockingStrategy]


# ---------------------------------------------------------------------------
# Per-component simulation types — mirror the simulate-component API contract
# ---------------------------------------------------------------------------


class SimulationStrategy(int, Enum):
    """Simulation strategy matching the simulate-component API.

    Integer values are part of the cross-language API contract — do not reorder.
    """

    LLM = 0
    MOCKITO = 1
    STATIC = 2


class RuleOperator(int, Enum):
    """Comparison operator for Mockito condition matching.

    Integer values are part of the cross-language API contract — do not reorder.
    """

    EQ = 0
    NE = 1
    GT = 2
    GTE = 3
    LT = 4
    LTE = 5
    CONTAINS = 6


class SimulationAnswerType(int, Enum):
    """Answer type for a Mockito simulation behavior.

    Integer values are part of the cross-language API contract — do not reorder.
    """

    RETURN = 0
    RAISE = 1


class SimulationAnswer(BaseModel):
    type: SimulationAnswerType = SimulationAnswerType.RETURN
    value: Any = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class SimulationCondition(BaseModel):
    field: str
    op: RuleOperator = RuleOperator.EQ
    value: Any = None

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class SimulationBehavior(BaseModel):
    when: list[SimulationCondition] | None = None
    then: list[SimulationAnswer]

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class ComponentSimulationConfig(BaseModel):
    """Per-component simulation config matching the simulate-component API request schema.

    Runtime-injected fields (workloadId, runId, input, traceId, parentSpanId,
    folderKey) are supplied at call time. inputSchema and outputSchema can be
    overridden here; if omitted they are derived from the function annotations.
    """

    component_id: str = Field(..., alias="componentId")
    component_type: str | None = Field(None, alias="componentType")
    component_description: str | None = Field(None, alias="componentDescription")
    simulation_instruction: str | None = Field(None, alias="simulationInstruction")
    simulation_strategy: SimulationStrategy = Field(
        SimulationStrategy.LLM, alias="simulationStrategy"
    )
    mock_value: Any = Field(None, alias="mockValue")
    behaviors: list[SimulationBehavior] | None = None
    input_schema: dict[str, Any] | None = Field(None, alias="inputSchema")
    output_schema: dict[str, Any] | None = Field(None, alias="outputSchema")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class MockingContext(BaseModel):
    """Execution context for mocking, holding strategy and inputs."""

    strategy: MockingStrategy | None
    inputs: dict[str, Any] = Field(default_factory=lambda: {})
    name: str = Field(default="debug")
    # When set, SimulateComponentMocker routes each tool call to the simulate-component API.
    components: list[ComponentSimulationConfig] | None = None
    workload_id: str | None = None


class SimulationConfig(BaseModel):
    """Top-level schema for simulation.json / --simulation flag.

    New format (routes to simulate-component API):
        {
            "enabled": true,
            "components": [
                {
                    "componentId": "my_tool",
                    "componentType": "tool",
                    "simulationStrategy": 0,
                    "simulationInstruction": "Simulate this tool by..."
                }
            ]
        }

    Legacy format (routes to local LLM mocker):
        {
            "enabled": true,
            "toolsToSimulate": [{"name": "my_tool"}],
            "instructions": "Simulate these tools by..."
        }
    """

    enabled: bool = True
    # New per-component format — when non-empty, routes to simulate-component API.
    components: list[ComponentSimulationConfig] = Field(default_factory=list)
    # Legacy flat format — used when components is empty; routes to local LLM mocker.
    tools_to_simulate: list[ToolSimulation] = Field(
        default_factory=list, alias="toolsToSimulate"
    )
    instructions: str = ""
    model: str | None = None

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class ExampleCall(BaseModel):
    """Example call for a resource containing resource I/O."""

    id: str = Field(..., alias="id")
    input: str = Field(..., alias="input")
    output: str = Field(..., alias="output")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )
