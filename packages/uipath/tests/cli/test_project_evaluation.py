import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from click.testing import CliRunner
from pydantic import BaseModel

from uipath._cli import cli
from uipath._cli._debug._project_evaluation import (
    ProjectEvaluationPlan,
    execute_project_evaluation,
)
from uipath._cli._utils._tracing import create_trace_manager
from uipath.eval.evaluators.evaluator_factory import EvaluatorFactory
from uipath.eval.models.models import ScoreType
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)


@pytest.mark.parametrize("operator, score", [("*", 1), ("+", 0)])
@pytest.mark.parametrize(
    "wire_fields",
    [{}, {"evaluatorTypeId": None}, {"evaluatorTypeId": None, "version": None}],
    ids=["file-config", "null-type", "null-type-and-version"],
)
async def test_project_evaluator_can_score_the_agent_trace(
    monkeypatch, operator, score, wire_fields
):
    project = Path(__file__).resolve().parents[2] / "samples" / "calculator"
    monkeypatch.chdir(project)
    config_file = project / "evaluations/evaluators/correct-operator-evaluator.json"
    config = {**json.loads(config_file.read_text()), **wire_fields}
    plan = ProjectEvaluationPlan.model_validate(
        {
            "evaluationItemId": "calculator-item",
            "evaluatorConfigs": [config],
            "evaluationCriterias": {config["id"]: {"operator": operator}},
        }
    )
    manager = create_trace_manager()
    tracer = manager.tracer_provider.get_tracer(__name__)

    async def execute(inputs, options):
        with tracer.start_as_current_span("track_operator") as span:
            span.set_attribute("input.value", json.dumps(inputs))
        return UiPathRuntimeResult(output={"value": 42})

    try:
        result = await execute_project_evaluation(
            SimpleNamespace(execute=execute),
            {"operator": "*"},
            UiPathExecuteOptions(),
            plan,
            manager,
        )
    finally:
        manager.shutdown()

    output = result.output
    assert isinstance(output, dict)
    assert output["executionOutput"] == {"value": 42}
    assert output["evaluationItemId"] == "calculator-item"
    [evaluator_run] = output["evaluatorResults"]
    assert evaluator_run["evaluatorId"] == config["id"]
    assert evaluator_run["score"] == score
    assert "error" not in evaluator_run


async def test_a_reference_outside_the_project_is_an_evaluator_error(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    plan = ProjectEvaluationPlan.model_validate(
        {
            "evaluationItemId": "item",
            "evaluatorConfigs": [
                {"id": "custom", "evaluatorSchema": "file://../outside.py:Evaluator"}
            ],
        }
    )
    manager = create_trace_manager()

    async def execute(inputs, options):
        return UiPathRuntimeResult(output={"answer": "Paris"})

    try:
        result = await execute_project_evaluation(
            SimpleNamespace(execute=execute), {}, UiPathExecuteOptions(), plan, manager
        )
    finally:
        manager.shutdown()

    output = result.output
    assert isinstance(output, dict)
    assert output["executionOutput"] == {"answer": "Paris"}
    [evaluator_run] = output["evaluatorResults"]
    assert evaluator_run["error"]["code"] == "ProjectEvaluatorFailed"


def test_debug_rejects_an_invalid_project_evaluation_plan():
    result = CliRunner().invoke(cli, ["debug", "main", "--evaluation-plan", "{}"])

    assert result.exit_code == 2
    assert "Invalid project evaluation plan." in result.output


async def test_faulted_debug_execution_preserves_the_runtime_result():
    plan = ProjectEvaluationPlan(
        evaluationItemId="item", evaluatorConfigs=[{"id": "custom"}]
    )
    fault = UiPathRuntimeResult(status=UiPathRuntimeStatus.FAULTED)
    runtime = SimpleNamespace(execute=AsyncMock(return_value=fault))
    manager = create_trace_manager()
    try:
        result = await execute_project_evaluation(
            runtime, {}, UiPathExecuteOptions(), plan, manager
        )
    finally:
        manager.shutdown()

    assert result is fault


@pytest.mark.parametrize("expected_output", [None, {"answer": "Paris"}])
async def test_project_evaluation_passes_criteria_and_serializes_model_output(
    tmp_path, monkeypatch, expected_output
):
    class Answer(BaseModel):
        answer: str

    class Criteria(BaseModel):
        expected_output: Answer | None = None
        expected_agent_behavior: str = ""

    monkeypatch.chdir(tmp_path)
    (tmp_path / "evaluator.py").touch()
    validate = AsyncMock(
        return_value=SimpleNamespace(
            score_type=ScoreType.NUMERICAL, score=0.75, details=None
        )
    )
    create_evaluator = Mock(
        return_value=SimpleNamespace(
            name="Project evaluator",
            evaluation_criteria_type=Criteria,
            validate_and_evaluate_criteria=validate,
        )
    )
    monkeypatch.setattr(EvaluatorFactory, "create_evaluator", create_evaluator)
    plan = ProjectEvaluationPlan(
        evaluationItemId="item",
        evaluatorConfigs=[
            {"id": "custom", "evaluatorSchema": "file://evaluator.py:Evaluator"}
        ],
        evaluationCriterias={"custom": {"expectedOutput": None}},
        expectedOutput=expected_output,
        expectedBehavior="Answer with the city.",
    )
    runtime = SimpleNamespace(
        execute=AsyncMock(
            return_value=UiPathRuntimeResult(output=Answer(answer="Paris"))
        )
    )

    manager = create_trace_manager()
    try:
        result = await execute_project_evaluation(
            runtime, {}, UiPathExecuteOptions(), plan, manager
        )
    finally:
        manager.shutdown()

    assert validate.call_args.args[1] == {
        "expectedAgentBehavior": "Answer with the city.",
        **({"expectedOutput": expected_output} if expected_output is not None else {}),
    }
    output = result.output
    assert isinstance(output, dict)
    assert output["executionOutput"] == {"answer": "Paris"}
    [evaluator_run] = output["evaluatorResults"]
    assert evaluator_run["score"] == 0.75
    assert evaluator_run["scoreType"] == 2
