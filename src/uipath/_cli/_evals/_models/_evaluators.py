from typing import List

from pydantic import BaseModel

from uipath.eval.models import (
    AgentExecutionOutput,
    EvalItemResult,
    EvaluationResult,
    EvaluatorCategory,
    EvaluatorType,
)


class EvaluationSetResult(BaseModel):
    """Result of a complete evaluation set."""

    eval_set_id: str
    eval_set_name: str
    results: List[EvaluationResult]
    average_score: float


class SwProgressItem(BaseModel):
    eval_run_id: str
    eval_results: list[EvalItemResult]
    success: bool
    agent_execution_output: AgentExecutionOutput


class EvaluatorBaseParams(BaseModel):
    """Parameters for initializing the base evaluator."""

    evaluator_id: str
    category: EvaluatorCategory
    evaluator_type: EvaluatorType
    name: str
    description: str
    created_at: str
    updated_at: str
    target_output_key: str
