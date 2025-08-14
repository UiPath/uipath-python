from enum import IntEnum
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class EvaluationItem(BaseModel):
    """Individual evaluation item within an evaluation set."""

    id: str
    name: str
    inputs: Dict[str, Any]
    expectedOutput: Dict[str, Any]
    expectedAgentBehavior: str = ""
    simulationInstructions: str = ""
    simulateInput: bool = False
    inputGenerationInstructions: str = ""
    simulateTools: bool = False
    toolsToSimulate: List[str] = Field(default_factory=list)
    evalSetId: str
    createdAt: str
    updatedAt: str


class EvaluationSet(BaseModel):
    """Complete evaluation set model."""

    id: str
    fileName: str
    evaluatorRefs: List[str] = Field(default_factory=list)
    evaluations: List[EvaluationItem] = Field(default_factory=list)
    name: str
    batchSize: int = 10
    timeoutMinutes: int = 20
    modelSettings: List[Dict[str, Any]] = Field(default_factory=list)
    createdAt: str
    updatedAt: str

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
