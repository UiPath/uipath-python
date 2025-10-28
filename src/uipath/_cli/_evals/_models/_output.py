import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from opentelemetry.sdk.trace import ReadableSpan
from pydantic import BaseModel, ConfigDict, model_serializer
from pydantic.alias_generators import to_camel
from pydantic_core import core_schema

from uipath._cli._runtime._contracts import UiPathRuntimeResult
from uipath.eval.models.models import (
    EvaluationResult,
    ScoreType,
    TrajectoryEvaluationTrace,
)


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


class EvaluationResultDto(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    score: float
    details: Optional[str | BaseModel] = None
    evaluation_time: Optional[float] = None

    @model_serializer(mode="wrap")
    def serialize_model(
        self,
        serializer: core_schema.SerializerFunctionWrapHandler,
        info: core_schema.SerializationInfo,
    ) -> Any:
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
    evaluator_id: str
    result: EvaluationResultDto


class EvaluationRunResult(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    evaluation_name: str
    evaluation_run_results: List[EvaluationRunResultDto]
    agent_execution_output: Optional[UiPathSerializableEvalRunExecutionOutput] = None

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
    evaluation_set_results: List[EvaluationRunResult]

    @property
    def score(self) -> float:
        """Compute overall average score from evaluation results."""
        if not self.evaluation_set_results:
            return 0.0

        eval_item_scores = [
            eval_result.score for eval_result in self.evaluation_set_results
        ]
        return sum(eval_item_scores) / len(eval_item_scores)

    def calculate_final_score(
        self,
        evaluator_weights: Dict[str, float] | None = None,
        default_weight: float = 1.0,
    ) -> tuple[float, Dict[str, float]]:
        """Aggregate evaluation results with deduplication and weighted scoring.

        This function performs the following steps:
        1. Flattens the nested evaluation_set_results structure
        2. Deduplicates results by datapoint_id (evaluation_name) and evaluator_name (averages duplicates)
        3. Calculates average score per evaluator across all datapoints
        4. Computes final weighted score across evaluators

        Args:
            evaluator_weights: Optional dict mapping evaluator names to weights
            default_weight: Default weight for evaluators not in evaluator_weights (default: 1.0)

        Returns:
            Tuple of (final_score, agg_metrics_per_evaluator)
            - final_score: Weighted average across evaluators
            - agg_metrics_per_evaluator: Dict mapping evaluator names to their average scores
        """
        if not self.evaluation_set_results:
            return 0.0, {}

        if evaluator_weights is None:
            evaluator_weights = {}

        # Step 1: Flatten the nested structure and group by datapoint_id and evaluator_name for deduplication
        # datapoint_id = evaluation_name, evaluator_name from EvaluationRunResultDto
        grouped_by_datapoint_evaluator: defaultdict[
            str, defaultdict[str, list[float]]
        ] = defaultdict(lambda: defaultdict(list))

        for eval_run_result in self.evaluation_set_results:
            datapoint_id = eval_run_result.evaluation_name
            for eval_run_result_dto in eval_run_result.evaluation_run_results:
                evaluator_name = eval_run_result_dto.evaluator_name
                score = eval_run_result_dto.result.score
                grouped_by_datapoint_evaluator[datapoint_id][evaluator_name].append(
                    score
                )

        # Step 2: Deduplicate by averaging same evaluator results for same datapoint
        dedup_scores: list[tuple[str, str, float]] = []
        for datapoint_id, evaluators_dict in grouped_by_datapoint_evaluator.items():
            for evaluator_name, scores_list in evaluators_dict.items():
                if scores_list:
                    # Average the scores for this evaluator on this datapoint
                    avg_score = sum(scores_list) / len(scores_list)
                    dedup_scores.append((datapoint_id, evaluator_name, avg_score))

        # Step 3: Group by evaluator and calculate average score per evaluator
        grouped_by_evaluator: defaultdict[str, list[float]] = defaultdict(list)
        for _datapoint_id, evaluator_name, score in dedup_scores:
            grouped_by_evaluator[evaluator_name].append(score)

        agg_metrics_per_evaluator = {}
        for evaluator_name, scores_list in grouped_by_evaluator.items():
            avg_score = sum(scores_list) / len(scores_list)
            agg_metrics_per_evaluator[evaluator_name] = avg_score

        # Step 4: Calculate final weighted score
        if not agg_metrics_per_evaluator:
            return 0.0, {}

        total_weighted_score = 0.0
        total_weight = 0.0

        for evaluator_name, avg_score in agg_metrics_per_evaluator.items():
            weight = evaluator_weights.get(evaluator_name, default_weight)
            total_weighted_score += avg_score * weight
            total_weight += weight

        final_score = total_weighted_score / total_weight if total_weight > 0 else 0.0

        return final_score, agg_metrics_per_evaluator
