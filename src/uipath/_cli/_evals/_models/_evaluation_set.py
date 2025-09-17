from enum import IntEnum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class EvaluationItem(BaseModel):
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

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    file_name: str
    evaluator_refs: List[str] = Field(default_factory=list)
    evaluations: List[EvaluationItem] = Field(default_factory=list)
    name: str
    batch_size: int = 10
    timeout_minutes: int = 20
    model_settings: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str

    def extract_selected_evals(self, eval_ids) -> None:
        selected_evals: list[EvaluationItem] = []
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
