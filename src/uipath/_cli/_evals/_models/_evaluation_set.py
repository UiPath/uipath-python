from enum import IntEnum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class EvaluationSimulationTool(BaseModel):
    name: str = Field(..., alias="name")


class EvaluationItem(BaseModel):
    """Individual evaluation item within an evaluation set."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    name: str
    inputs: Dict[str, Any]
    expected_output: Dict[str, Any]
    expected_agent_behavior: str = Field(default="", alias="expectedAgentBehavior")
    simulation_instructions: str = Field(default="", alias="simulationInstructions")
    simulate_input: bool = Field(default=False, alias="simulateInput")
    input_generation_instructions: str = Field(
        default="", alias="inputGenerationInstructions"
    )
    simulate_tools: bool = Field(default=False, alias="simulateTools")
    tools_to_simulate: List[EvaluationSimulationTool] = Field(
        default_factory=list, alias="toolsToSimulate"
    )
    eval_set_id: str = Field(alias="evalSetId")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class EvaluationSet(BaseModel):
    """Complete evaluation set model."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    file_name: str = Field(..., alias="fileName")
    evaluator_refs: List[str] = Field(default_factory=list)
    evaluations: List[EvaluationItem] = Field(default_factory=list)
    name: str
    batch_size: int = Field(10, alias="batchSize")
    timeout_minutes: int = Field(default=20, alias="timeoutMinutes")
    model_settings: List[Dict[str, Any]] = Field(
        default_factory=list, alias="modelSettings"
    )
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")

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
