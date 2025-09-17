from typing import List, Optional

from opentelemetry.sdk.trace import ReadableSpan
from pydantic import BaseModel, ConfigDict, model_serializer
from pydantic.alias_generators import to_camel

from uipath._cli._runtime._contracts import UiPathRuntimeResult
from uipath.eval.models.models import EvaluationResult, ScoreType


class UiPathEvalRunExecutionOutput(BaseModel):
    """Result of a single agent response."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    execution_time: float
    spans: list[ReadableSpan]
    result: UiPathRuntimeResult


class EvaluationResultDto(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    score: float
    details: Optional[str] = None
    evaluation_time: Optional[float] = None

    @model_serializer(mode="wrap")
    def serialize_model(self, serializer, info):
        data = serializer(self)
        if self.details is None and isinstance(data, dict):
            data.pop("details", None)
        return data

    @classmethod
    def from_evaluation_result(
        cls, evaluation_result: EvaluationResult
    ) -> "EvaluationResultDto":
        score_type = evaluation_result.score_type
        score: float
        if score_type == ScoreType.BOOLEAN:
            score = 100 if evaluation_result.score else 0
        elif score_type == ScoreType.ERROR:
            score = 0
        else:
            score = evaluation_result.score

        return cls(
            score=score,
            details=evaluation_result.details,
            evaluation_time=evaluation_result.evaluation_time,
        )


class EvaluationRunResultDto(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    evaluator_name: str
    result: EvaluationResultDto


class EvaluationRunResult(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    evaluation_name: str
    evaluation_run_results: List[EvaluationRunResultDto]


class UiPathEvalOutput(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    evaluation_set_name: str
    score: float
    evaluation_set_results: List[EvaluationRunResult]

    def compute_average_score(self) -> None:
        total_score = 0.0
        total_count = 0

        for evaluation_set_result in self.evaluation_set_results:
            for evaluation_run_result in evaluation_set_result.evaluation_run_results:
                total_score += evaluation_run_result.result.score
                total_count += 1

        self.score = total_score / total_count if total_count > 0 else 0.0
