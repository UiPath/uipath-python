from typing import Dict, List

from pydantic import BaseModel

from uipath._cli._evals._models._evaluation_set import EvaluationResultExtended
from uipath.eval.models import (
    AgentExecutionOutput,
    EvalItemResult,
    EvaluatorCategory,
    EvaluatorType,
)


class EvaluationRunResult(BaseModel):
    """Result of a single evaluation run."""
    
    results: List[EvaluationResultExtended]
    average_score: float


class EvaluationSetResult(BaseModel):
    """Result of a complete evaluation set."""

    eval_set_id: str
    eval_set_name: str
    runs: Dict[str, EvaluationRunResult]  # Group results by run name
    overall_average_score: float


class SwProgressItem(BaseModel):
    eval_run_id: str
    eval_results: list[EvalItemResult]
    success: bool
    agent_execution_output: AgentExecutionOutput


class EvaluatorBaseParams(BaseModel):
    """Parameters for initializing the base evaluator."""

    category: EvaluatorCategory
    evaluator_type: EvaluatorType
    name: str
    description: str
    created_at: str
    updated_at: str
    target_output_key: str
