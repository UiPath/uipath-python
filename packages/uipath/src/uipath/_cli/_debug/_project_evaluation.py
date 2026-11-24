from pathlib import Path
from time import monotonic
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from uipath.core.tracing import UiPathTraceManager
from uipath.eval._execution_context import (
    ExecutionSpanCollector,
    execution_id_context,
    span_collector_context,
)
from uipath.eval.constants import CUSTOM_EVALUATOR_PREFIX, EVALS_FOLDER
from uipath.eval.evaluators.evaluator_factory import EvaluatorFactory
from uipath.eval.models.models import ScoreType, WorkloadExecution
from uipath.eval.runtime._exporters import ExecutionSpanExporter, ExecutionSpanProcessor
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)


class ProjectEvaluationPlan(BaseModel):
    """Inputs for scoring one debug execution inside its project."""

    model_config = ConfigDict(alias_generator=to_camel)

    evaluation_item_id: str
    evaluator_configs: list[dict[str, Any]] = Field(min_length=1)
    evaluation_criterias: dict[str, dict[str, Any] | None] | None = None
    expected_output: Any = None
    expected_behavior: str | None = None


def _resolve_schema(schema: str) -> str:
    reference = schema.removeprefix(CUSTOM_EVALUATOR_PREFIX)
    file_name, separator, class_name = reference.rpartition(":")
    if reference == schema or not separator or not class_name:
        raise ValueError("A project evaluator requires a Python file and class name.")

    relative = Path(file_name)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix != ".py":
        raise ValueError("A project evaluator must reference a relative Python file.")

    root = Path.cwd().resolve()
    evaluators = root / EVALS_FOLDER / "evaluators"
    for directory in (root, evaluators, evaluators / "custom"):
        path = (directory / relative).resolve()
        if path.is_relative_to(root) and path.is_file():
            return f"{CUSTOM_EVALUATOR_PREFIX}{path}:{class_name}"

    raise ValueError(f"Project evaluator file '{file_name}' was not found.")


async def _score(
    config: dict[str, Any], plan: ProjectEvaluationPlan, workload: WorkloadExecution
) -> dict[str, Any]:
    evaluator_id = config["id"]
    start = monotonic()
    try:
        definition = {
            **config,
            "evaluatorSchema": _resolve_schema(config["evaluatorSchema"]),
        }
        if definition.get("version") is None:
            definition["version"] = "1.0"
        if definition.get("evaluatorTypeId") is None:
            definition.pop("evaluatorTypeId", None)
        evaluator = EvaluatorFactory.create_evaluator(definition)
        criteria = dict((plan.evaluation_criterias or {}).get(evaluator_id) or {})
        fields = evaluator.evaluation_criteria_type.model_fields
        if "expected_output" in fields and criteria.get("expectedOutput") is None:
            if plan.expected_output is not None:
                criteria["expectedOutput"] = plan.expected_output
            else:
                criteria.pop("expectedOutput", None)
        if "expected_agent_behavior" in fields and plan.expected_behavior is not None:
            criteria.setdefault("expectedAgentBehavior", plan.expected_behavior)

        result = await evaluator.validate_and_evaluate_criteria(
            workload, criteria or None
        )
        if result.score_type == ScoreType.ERROR:
            raise ValueError(str(result.details or "The evaluator returned an error."))

        details = result.details
        structured = (
            details.model_dump(mode="json") if isinstance(details, BaseModel) else {}
        )
        justification = structured.get("justification") if structured else details
        return {
            "evaluatorId": evaluator_id,
            "evaluatorName": evaluator.name,
            "score": float(result.score),
            "scoreType": 1 if result.score_type == ScoreType.BOOLEAN else 2,
            "details": str(details) if details is not None else None,
            "justification": justification,
            "expectedOutput": structured.get("expected", plan.expected_output),
            "actualOutput": structured.get("actual", workload.workload_output),
            "evaluationTimeSeconds": monotonic() - start,
        }
    except Exception as error:
        return {
            "evaluatorId": evaluator_id,
            "evaluatorName": config.get("name"),
            "score": 0,
            "scoreType": 0,
            "evaluationTimeSeconds": monotonic() - start,
            "error": {"code": "ProjectEvaluatorFailed", "message": str(error)},
        }


async def execute_project_evaluation(
    runtime: UiPathRuntimeProtocol,
    inputs: dict[str, Any] | None,
    options: UiPathExecuteOptions,
    plan: ProjectEvaluationPlan,
    trace_manager: UiPathTraceManager,
) -> UiPathRuntimeResult:
    """Run the agent once and score its output with code from the same project."""
    collector = ExecutionSpanCollector()
    processor = ExecutionSpanProcessor(ExecutionSpanExporter(), collector)
    trace_manager.tracer_provider.add_span_processor(processor)
    execution_token = execution_id_context.set(plan.evaluation_item_id)
    collector_token = span_collector_context.set(collector)
    try:
        result = await runtime.execute(inputs, options=options)
    finally:
        span_collector_context.reset(collector_token)
        execution_id_context.reset(execution_token)

    if result.status != UiPathRuntimeStatus.SUCCESSFUL:
        return result

    output = result.output
    if isinstance(output, BaseModel):
        output = output.model_dump(mode="json")
    workload = WorkloadExecution(
        agent_input=inputs,
        workload_output=output if output is not None else {},
        workload_trace=collector.get_spans(plan.evaluation_item_id),
        expected_agent_behavior=plan.expected_behavior,
    )
    evaluator_results = [
        await _score(config, plan, workload) for config in plan.evaluator_configs
    ]
    return result.model_copy(
        update={
            "output": {
                "evaluationItemId": plan.evaluation_item_id,
                "executionOutput": output,
                "evaluatorResults": evaluator_results,
            }
        }
    )
