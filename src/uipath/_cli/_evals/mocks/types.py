from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class MockingStrategyType(str, Enum):
    LLM = "llm"
    MOCKITO = "mockito"
    UNKNOWN = "unknown"


class BaseMockingStrategy(BaseModel):
    pass


class ToolSimulation(BaseModel):
    name: str = Field(..., alias="name")


class ModelSettings(BaseModel):
    """Model Generation Parameters."""

    model: str = Field(..., alias="model")
    temperature: float | str | None = Field(default=None, alias="temperature")
    top_p: float | None = Field(default=None, alias="topP")
    top_k: int | None = Field(default=None, alias="topK")
    frequency_penalty: float | None = Field(default=None, alias="frequencyPenalty")
    presence_penalty: float | None = Field(default=None, alias="presencePenalty")
    max_tokens: int | None = Field(default=None, alias="maxTokens")


class LLMMockingStrategy(BaseMockingStrategy):
    type: Literal[MockingStrategyType.LLM] = MockingStrategyType.LLM
    prompt: str = Field(..., alias="prompt")
    tools_to_simulate: list[ToolSimulation] = Field(..., alias="toolsToSimulate")
    model: ModelSettings | None = Field(None, alias="model")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class InputMockingStrategy(BaseModel):
    prompt: str = Field(..., alias="prompt")
    model: ModelSettings | None = Field(None, alias="model")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class MockingArgument(BaseModel):
    args: list[Any] = Field(default_factory=lambda: [], alias="args")
    kwargs: dict[str, Any] = Field(default_factory=lambda: {}, alias="kwargs")


class MockingAnswerType(str, Enum):
    RETURN = "return"
    RAISE = "raise"


class MockingAnswer(BaseModel):
    type: MockingAnswerType
    value: Any = Field(..., alias="value")


class MockingBehavior(BaseModel):
    function: str = Field(..., alias="function")
    arguments: MockingArgument | None = Field(default=None, alias="arguments")
    then: list[MockingAnswer] = Field(..., alias="then")


class MockitoMockingStrategy(BaseMockingStrategy):
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
    type: str = Field(..., alias="type")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


MockingStrategy = Union[KnownMockingStrategy, UnknownMockingStrategy]


class MockingContext(BaseModel):
    strategy: MockingStrategy | None
    inputs: dict[str, Any] = Field(default_factory=lambda: {})
    name: str = Field(default="debug")
