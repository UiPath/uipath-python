from enum import Enum, IntEnum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class EvaluatorReference(BaseModel):
    """Reference to an evaluator with optional weight.

    Can be constructed from:
    - A string (evaluator ID): EvaluatorReference(ref="evaluator-id")
    - A dict with ref and optional weight: EvaluatorReference(ref="evaluator-id", weight=2.0)
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    ref: str = Field(..., description="Path to the evaluator configuration file")
    weight: float = Field(
        default=1.0,
        description="Weight for this evaluator in scoring calculations",
        ge=0,
    )

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> Any:
        """Allow creating EvaluatorReference from a string or dict."""
        from pydantic_core import core_schema

        def validate_from_str(value: str) -> dict[str, Any]:
            """Convert a string to a dict with ref field."""
            return {"ref": value}

        def serialize(instance: "EvaluatorReference") -> Any:
            if instance.weight != 1.0:
                return {"ref": instance.ref, "weight": instance.weight}
            return instance.ref

        python_schema = handler(source_type)
        return core_schema.union_schema(
            [
                core_schema.chain_schema(
                    [
                        core_schema.str_schema(),
                        core_schema.no_info_plain_validator_function(validate_from_str),
                        python_schema,
                    ]
                ),
                python_schema,
            ],
            serialization=core_schema.plain_serializer_function_ser_schema(serialize),
        )


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
    simulate_input: Optional[bool] = Field(default=None, alias="simulateInput")
    input_generation_instructions: Optional[str] = Field(
        default=None, alias="inputGenerationInstructions"
    )
    simulate_tools: Optional[bool] = Field(default=None, alias="simulateInput")
    simulation_instructions: Optional[str] = Field(
        default=None, alias="simulationInstructions"
    )
    tools_to_simulate: list[EvaluationSimulationTool] = Field(
        default_factory=list, alias="toolsToSimulate"
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
    evaluator_configs: List[EvaluatorReference] = Field(
        default_factory=list, alias="evaluatorConfigs"
    )
    evaluations: List[EvaluationItem] = Field(default_factory=list)

    def extract_selected_evals(self, eval_ids) -> None:
        selected_evals: list[EvaluationItem] = []
        remaining_ids = set(eval_ids)
        for evaluation in self.evaluations:
            if evaluation.id in remaining_ids:
                selected_evals.append(evaluation)
                remaining_ids.remove(evaluation.id)
        if len(remaining_ids) > 0:
            raise ValueError("Unknown evaluation ids: {}".format(remaining_ids))
        self.evaluations = selected_evals


class LegacyEvaluationSet(BaseModel):
    """Complete evaluation set model."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    file_name: str = Field(..., alias="fileName")
    evaluator_refs: List[str] = Field(default_factory=list)
    evaluator_configs: List[EvaluatorReference] = Field(
        default_factory=list, alias="evaluatorConfigs"
    )
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
        remaining_ids = set(eval_ids)
        for evaluation in self.evaluations:
            if evaluation.id in remaining_ids:
                selected_evals.append(evaluation)
                remaining_ids.remove(evaluation.id)
        if len(remaining_ids) > 0:
            raise ValueError("Unknown evaluation ids: {}".format(remaining_ids))
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
