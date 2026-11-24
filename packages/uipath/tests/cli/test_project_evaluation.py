import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from uipath._cli._debug._project_evaluation import (
    ProjectEvaluationPlan,
    execute_project_evaluation,
)
from uipath._cli._utils._tracing import create_trace_manager
from uipath.runtime import UiPathExecuteOptions, UiPathRuntimeResult


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

    assert result.output["executionOutput"] == {"value": 42}
    assert result.output["evaluationItemId"] == "calculator-item"
    [evaluator_run] = result.output["evaluatorResults"]
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

    assert result.output["executionOutput"] == {"answer": "Paris"}
    [evaluator_run] = result.output["evaluatorResults"]
    assert evaluator_run["error"]["code"] == "ProjectEvaluatorFailed"
