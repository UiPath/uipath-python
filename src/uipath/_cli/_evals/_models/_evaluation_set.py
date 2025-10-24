from enum import Enum, IntEnum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag
from pydantic.alias_generators import to_camel

from uipath.eval.evaluators import BaseEvaluator, LegacyBaseEvaluator


class EvaluationSimulationTool(BaseModel):
    name: str = Field(..., alias="name")


class MockingStrategyType(str, Enum):
    LLM = "llm"
    MOCKITO = "mockito"
    UNKNOWN = "unknown"


class BaseMockingStrategy(BaseModel):
    pass


class ModelSettings(BaseModel):
    """Model Generation Parameters."""

    model: str = Field(..., alias="model")
    temperature: Optional[float] = Field(default=None, alias="temperature")
    top_p: Optional[float] = Field(default=None, alias="topP")
    top_k: Optional[int] = Field(default=None, alias="topK")
    frequency_penalty: Optional[float] = Field(default=None, alias="frequencyPenalty")
    presence_penalty: Optional[float] = Field(default=None, alias="presencePenalty")
    max_tokens: Optional[int] = Field(default=None, alias="maxTokens")


class LLMMockingStrategy(BaseMockingStrategy):
    type: Literal[MockingStrategyType.LLM] = MockingStrategyType.LLM
    prompt: str = Field(..., alias="prompt")
    tools_to_simulate: list[EvaluationSimulationTool] = Field(
        ..., alias="toolsToSimulate"
    )
    model: Optional[ModelSettings] = Field(None, alias="model")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class InputMockingStrategy(BaseModel):
    prompt: str = Field(..., alias="prompt")
    model: Optional[ModelSettings] = Field(None, alias="model")

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class MockingArgument(BaseModel):
    args: List[Any] = Field(default_factory=lambda: [], alias="args")
    kwargs: Dict[str, Any] = Field(default_factory=lambda: {}, alias="kwargs")


class MockingAnswerType(str, Enum):
    RETURN = "return"
    RAISE = "raise"


class MockingAnswer(BaseModel):
    type: MockingAnswerType
    value: Any = Field(..., alias="value")


class MockingBehavior(BaseModel):
    function: str = Field(..., alias="function")
    arguments: MockingArgument = Field(..., alias="arguments")
    then: List[MockingAnswer] = Field(..., alias="then")


class MockitoMockingStrategy(BaseMockingStrategy):
    type: Literal[MockingStrategyType.MOCKITO] = MockingStrategyType.MOCKITO
    behaviors: List[MockingBehavior] = Field(..., alias="config")

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


class EvaluationItem(BaseModel):
    """Individual evaluation item within an evaluation set."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    id: str
    name: str
    inputs: Dict[str, Any]
    evaluation_criterias: dict[str, dict[str, Any] | None] = Field(
        ..., alias="evaluationCriterias"
    )
    expected_agent_behavior: str = Field(default="", alias="expectedAgentBehavior")
    mocking_strategy: Optional[MockingStrategy] = Field(
        default=None,
        alias="mockingStrategy",
    )
    input_mocking_strategy: Optional[InputMockingStrategy] = Field(
        default=None,
        alias="inputMockingStrategy",
    )


class LegacyEvaluationItem(BaseModel):
    """Individual evaluation item within an evaluation set."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="allow"
    )

    id: str
    name: str
    inputs: Dict[str, Any]
    expected_output: Dict[str, Any]
    expected_agent_behavior: str = Field(default="", alias="expectedAgentBehavior")
    eval_set_id: str = Field(alias="evalSetId")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    mocking_strategy: Optional[MockingStrategy] = Field(
        default=None,
        alias="mockingStrategy",
    )
    input_mocking_strategy: Optional[InputMockingStrategy] = Field(
        default=None,
        alias="inputMockingStrategy",
    )


class EvaluationSet(BaseModel):
    """Complete evaluation set model."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="allow"
    )

    id: str
    name: str
    version: Literal["1.0"] = "1.0"
    evaluator_refs: List[str] = Field(default_factory=list)
    evaluations: List[EvaluationItem] = Field(default_factory=list)

    def extract_selected_evals(self, eval_ids) -> None:
        selected_evals: list[EvaluationItem] = []
        for evaluation in self.evaluations:
            if evaluation.id in eval_ids:
                selected_evals.append(evaluation)
                eval_ids.remove(evaluation.id)
        if len(eval_ids) > 0:
            raise ValueError("Unknown evaluation ids: {}".format(eval_ids))
        self.evaluations = selected_evals


class LegacyEvaluationSet(BaseModel):
    """Complete evaluation set model."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    file_name: str = Field(..., alias="fileName")
    evaluator_refs: List[str] = Field(default_factory=list)
    evaluations: List[LegacyEvaluationItem] = Field(default_factory=list)
    name: str
    batch_size: int = Field(10, alias="batchSize")
    timeout_minutes: int = Field(default=20, alias="timeoutMinutes")
    model_settings: List[Dict[str, Any]] = Field(
        default_factory=list, alias="modelSettings"
    )
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

    def extract_selected_evals(self, eval_ids) -> None:
        selected_evals: list[LegacyEvaluationItem] = []
        for evaluation in self.evaluations:
            if evaluation.id in eval_ids:
                selected_evals.append(evaluation)
                eval_ids.remove(evaluation.id)
        if len(eval_ids) > 0:
            raise ValueError("Unknown evaluation ids: {}".format(eval_ids))
        self.evaluations = selected_evals


class EvaluationStatus(IntEnum):
    PENDING = 0
    IN_PROGRESS = 1
    COMPLETED = 2


def _discriminate_eval_set(
    v: Any,
) -> Literal["evaluation_set", "legacy_evaluation_set"]:
    """Discriminator function that returns a tag based on version field."""
    if isinstance(v, dict):
        version = v.get("version")
        if version == "1.0":
            return "evaluation_set"
    return "legacy_evaluation_set"


AnyEvaluationSet = Annotated[
    Union[
        Annotated[EvaluationSet, Tag("evaluation_set")],
        Annotated[LegacyEvaluationSet, Tag("legacy_evaluation_set")],
    ],
    Discriminator(_discriminate_eval_set),
]

AnyEvaluationItem = Union[EvaluationItem, LegacyEvaluationItem]
AnyEvaluator = Union[LegacyBaseEvaluator[Any], BaseEvaluator[Any, Any, Any]]
