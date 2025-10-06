from enum import IntEnum
from typing import Annotated, Any, Dict, List, Literal, Union

from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag
from pydantic.alias_generators import to_camel

from uipath.eval.coded_evaluators import BaseEvaluator
from uipath.eval.evaluators import LegacyBaseEvaluator


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


class LegacyEvaluationItem(BaseModel):
    """Individual evaluation item within an evaluation set."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    name: str
    inputs: Dict[str, Any]
    expected_output: Dict[str, Any]
    expected_agent_behavior: str = ""
    simulation_instructions: str = ""
    simulate_input: bool = False
    input_generation_instructions: str = ""
    simulate_tools: bool = False
    tools_to_simulate: List[str] = Field(default_factory=list)
    eval_set_id: str
    created_at: str
    updated_at: str


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
    file_name: str
    evaluator_refs: List[str] = Field(default_factory=list)
    evaluations: List[LegacyEvaluationItem] = Field(default_factory=list)
    name: str
    batch_size: int = 10
    timeout_minutes: int = 20
    model_settings: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str

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

AnyEvaluator = Annotated[
    Union[LegacyBaseEvaluator[Any], BaseEvaluator[Any, Any, Any]], "List of evaluators"
]
