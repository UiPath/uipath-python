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


class MockingContext(BaseModel):
    """Execution context for mocking, holding strategy and inputs."""

    strategy: MockingStrategy | None
    inputs: dict[str, Any] = Field(default_factory=lambda: {})
    name: str = Field(default="debug")


class ExampleCall(BaseModel):
    """Example call for a resource containing resource I/O."""

    id: str = Field(..., alias="id")
    input: str = Field(..., alias="input")
    output: str = Field(..., alias="output")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )
