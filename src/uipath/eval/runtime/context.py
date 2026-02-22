"""Context class for evaluation runs."""

from typing import Any

from uipath.runtime.schema import UiPathRuntimeSchema

from ..evaluators.base_evaluator import GenericBaseEvaluator
from ..models.evaluation_set import EvaluationSet


class UiPathEvalContext:
    """Context used for evaluation runs."""

    # Required Fields
    runtime_schema: UiPathRuntimeSchema
    evaluation_set: EvaluationSet
    evaluators: list[GenericBaseEvaluator[Any, Any, Any]]
    execution_id: str

    # Optional Fields
    entrypoint: str | None = None
    workers: int | None = 1
    eval_set_run_id: str | None = None
    verbose: bool = False
    enable_mocker_cache: bool = False
    report_coverage: bool = False
    input_overrides: dict[str, Any] | None = None
    resume: bool = False
    job_id: str | None = None
