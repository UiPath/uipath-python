"""Tests for UiPathEvalRuntime._generate_input_for_eval.

The runtime re-validates the simulated input through ``EvaluationItem`` instead
of ``model_copy(update=...)`` so malformed input is reported as an input-mocking
failure rather than an opaque ``MockingContext`` error (SRE-655743).
"""

import uuid
from typing import Any, AsyncGenerator

import pytest
from _pytest.monkeypatch import MonkeyPatch

from uipath.core.events import EventBus
from uipath.core.tracing import UiPathTraceManager
from uipath.eval.mocks._mocker import UiPathInputMockingError
from uipath.eval.models.evaluation_set import EvaluationItem
from uipath.eval.runtime import UiPathEvalContext, UiPathEvalRuntime
from uipath.eval.runtime import runtime as runtime_module
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeFactorySettings,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathRuntimeStorageProtocol,
    UiPathStreamOptions,
)
from uipath.runtime.schema import UiPathRuntimeSchema

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
}


class _TestRuntime:
    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        return UiPathRuntimeResult(output={}, status=UiPathRuntimeStatus.SUCCESSFUL)

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        yield UiPathRuntimeResult(output={}, status=UiPathRuntimeStatus.SUCCESSFUL)

    async def get_schema(self) -> UiPathRuntimeSchema:
        return _schema()

    async def dispose(self) -> None:
        pass


class _TestFactory:
    def discover_entrypoints(self) -> list[str]:
        return ["test"]

    async def get_storage(self) -> UiPathRuntimeStorageProtocol | None:
        return None

    async def get_settings(self) -> UiPathRuntimeFactorySettings | None:
        return None

    async def new_runtime(
        self, entrypoint: str, runtime_id: str, **kwargs: Any
    ) -> UiPathRuntimeProtocol:
        return _TestRuntime()

    async def dispose(self) -> None:
        pass


def _schema() -> UiPathRuntimeSchema:
    return UiPathRuntimeSchema(
        filePath="test.py",
        uniqueId="test",
        type="workflow",
        input=INPUT_SCHEMA,
        output={"type": "object", "properties": {}},
    )


def _eval_runtime() -> UiPathEvalRuntime:
    context = UiPathEvalContext()
    context.execution_id = str(uuid.uuid4())
    context.evaluation_set = None  # type: ignore[assignment]
    context.runtime_schema = _schema()
    context.evaluators = []
    return UiPathEvalRuntime(context, _TestFactory(), UiPathTraceManager(), EventBus())


def _eval_item() -> EvaluationItem:
    # Uses camelCase aliases throughout so the round-trip exercises alias
    # handling in the runtime's model_dump(by_alias=True) / model_validate.
    return EvaluationItem.model_validate(
        {
            "id": "test-eval-id",
            "name": "Test Input Generation",
            "inputs": {},
            "evaluationCriterias": {"Default Evaluator": {"result": 35}},
            "expectedAgentBehavior": "Agent should multiply the numbers",
            "inputMockingStrategy": {
                "prompt": "Generate a multiplication query with 5 and 7",
                "model": {
                    "model": "gpt-4o-mini-2024-07-18",
                    "temperature": 0.5,
                    "maxTokens": 150,
                },
            },
        }
    )


def _patch_generated_input(
    monkeypatch: MonkeyPatch, value: Any
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    async def _fake_generate_llm_input(*args: Any, **kwargs: Any) -> Any:
        calls.append({"args": args, "kwargs": kwargs})
        return value

    monkeypatch.setattr(runtime_module, "generate_llm_input", _fake_generate_llm_input)
    return calls


@pytest.mark.asyncio
async def test_generate_input_for_eval_round_trips_aliased_fields(
    monkeypatch: MonkeyPatch,
):
    calls = _patch_generated_input(monkeypatch, {"query": "Calculate 5 times 7"})
    eval_item = _eval_item()

    updated = await _eval_runtime()._generate_input_for_eval(eval_item)

    assert updated.inputs == {"query": "Calculate 5 times 7"}
    # Every aliased field survives the dump/validate round trip unchanged.
    assert updated.model_dump(by_alias=True) == {
        **eval_item.model_dump(by_alias=True),
        "inputs": {"query": "Calculate 5 times 7"},
    }
    assert updated.input_mocking_strategy is not None
    assert updated.input_mocking_strategy.model is not None
    assert updated.input_mocking_strategy.model.max_tokens == 150
    # The original item is left untouched.
    assert eval_item.inputs == {}

    assert len(calls) == 1
    assert calls[0]["args"][1] == INPUT_SCHEMA
    assert calls[0]["kwargs"]["expected_behavior"] == eval_item.expected_agent_behavior
    assert calls[0]["kwargs"]["expected_output"] == eval_item.evaluation_criterias


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_input",
    [
        pytest.param({1: "x"}, id="non-string-key"),
        pytest.param(["a"], id="list"),
        pytest.param('{"query": "stringified"}', id="stringified-object"),
    ],
)
async def test_generate_input_for_eval_reports_invalid_input_as_mocking_error(
    monkeypatch: MonkeyPatch, bad_input: Any
):
    _patch_generated_input(monkeypatch, bad_input)

    with pytest.raises(UiPathInputMockingError) as exc_info:
        await _eval_runtime()._generate_input_for_eval(_eval_item())

    message = str(exc_info.value)
    assert "Simulated input does not match the evaluation item schema" in message
    assert "ValidationError" in message
    assert "inputs" in message
