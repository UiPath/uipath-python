import logging

from opentelemetry.sdk.trace import ReadableSpan
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from uipath.runtime import UiPathRuntimeResult

from ..models.models import (
    EvaluationResultDto,
    TrajectoryEvaluationTrace,
)


class EvaluationRuntimeException(Exception):
    def __init__(self, spans, logs, root_exception, execution_time):
        self.spans = spans
        self.logs = logs
        self.root_exception = root_exception
        self.execution_time = execution_time


class UiPathEvalRunExecutionOutput(BaseModel):
    """Result of a single agent response."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    execution_time: float
    spans: list[ReadableSpan]
    logs: list[logging.LogRecord]
    result: UiPathRuntimeResult


class UiPathSerializableEvalRunExecutionOutput(BaseModel):
    execution_time: float
    trace: TrajectoryEvaluationTrace
    result: UiPathRuntimeResult


def convert_eval_execution_output_to_serializable(
    output: UiPathEvalRunExecutionOutput,
) -> UiPathSerializableEvalRunExecutionOutput:
    return UiPathSerializableEvalRunExecutionOutput(
        execution_time=output.execution_time,
        result=output.result,
        trace=TrajectoryEvaluationTrace.from_readable_spans(output.spans),
    )


class UiPathEvalRunResultDto(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    evaluator_name: str
    evaluator_id: str
    result: EvaluationResultDto


class UiPathEvalRunResult(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    evaluation_name: str
    evaluation_run_results: list[UiPathEvalRunResultDto]
    agent_execution_output: UiPathSerializableEvalRunExecutionOutput | None = None

    @property
    def score(self) -> float:
        """Compute average score for this single eval_item."""
        if not self.evaluation_run_results:
            return 0.0

        total_score = sum(dto.result.score for dto in self.evaluation_run_results)
        return total_score / len(self.evaluation_run_results)


class UiPathEvalOutput(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    evaluation_set_name: str
    evaluation_set_results: list[UiPathEvalRunResult]

    @property
    def score(self) -> float:
        """Compute overall average score from evaluation results."""
        if not self.evaluation_set_results:
            return 0.0

        eval_item_scores = [
            eval_result.score for eval_result in self.evaluation_set_results
        ]
        return sum(eval_item_scores) / len(eval_item_scores)
