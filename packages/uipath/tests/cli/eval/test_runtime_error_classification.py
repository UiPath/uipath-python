"""Tests for classifying eval execution errors as user vs runtime failures."""

import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

from uipath.core.events import EventBus
from uipath.core.tracing import UiPathTraceManager
from uipath.eval.helpers import EvalHelpers
from uipath.eval.runtime import UiPathEvalContext, evaluate
from uipath.eval.runtime.events import EvalRunUpdatedEvent, EvaluationEvents
from uipath.eval.runtime.runtime import _is_user_facing_error
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeFactorySettings,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
    UiPathRuntimeStorageProtocol,
    UiPathStreamOptions,
)
from uipath.runtime.errors import (
    UiPathErrorCategory,
    UiPathErrorCode,
    UiPathRuntimeError,
)
from uipath.runtime.schema import UiPathRuntimeSchema


def _make_error(category: UiPathErrorCategory) -> UiPathRuntimeError:
    return UiPathRuntimeError(
        UiPathErrorCode.FUNCTION_EXECUTION_ERROR,
        "Some failure",
        "details",
        category,
        include_traceback=False,
    )


def test_user_category_error_is_user_facing():
    assert _is_user_facing_error(_make_error(UiPathErrorCategory.USER)) is True


def test_system_category_error_is_not_user_facing():
    assert _is_user_facing_error(_make_error(UiPathErrorCategory.SYSTEM)) is False


def test_unknown_category_error_is_not_user_facing():
    assert _is_user_facing_error(_make_error(UiPathErrorCategory.UNKNOWN)) is False


def test_plain_exception_is_not_user_facing():
    assert _is_user_facing_error(ValueError("boom")) is False


class _FailingRuntime:
    """Runtime whose execution always raises the configured error."""

    def __init__(self, error: Exception):
        self._error = error

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        raise self._error

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        raise self._error
        yield  # unreachable; makes this an async generator

    async def get_schema(self) -> UiPathRuntimeSchema:
        return UiPathRuntimeSchema(
            filePath="test.py",
            uniqueId="test",
            type="workflow",
            input={"type": "object", "properties": {}},
            output={"type": "object", "properties": {}},
        )

    async def dispose(self) -> None:
        pass


class _FailingFactory:
    def __init__(self, error: Exception):
        self._error = error

    def discover_entrypoints(self) -> list[str]:
        return ["test"]

    async def get_storage(self) -> UiPathRuntimeStorageProtocol | None:
        return None

    async def get_settings(self) -> UiPathRuntimeFactorySettings | None:
        return None

    async def new_runtime(
        self, entrypoint: str, runtime_id: str, **kwargs
    ) -> UiPathRuntimeProtocol:
        return _FailingRuntime(self._error)

    async def dispose(self) -> None:
        pass


async def _run_failing_eval(error: Exception) -> list[EvalRunUpdatedEvent]:
    """Run an eval whose execution raises, returning captured run-updated events."""
    event_bus = EventBus()
    trace_manager = UiPathTraceManager()
    captured: list[EvalRunUpdatedEvent] = []

    async def capture(event: EvalRunUpdatedEvent) -> None:
        captured.append(event)

    event_bus.subscribe(EvaluationEvents.UPDATE_EVAL_RUN, capture)

    factory = _FailingFactory(error)
    eval_set_path = str(Path(__file__).parent / "evals" / "eval-sets" / "default.json")
    evaluation_set, _ = EvalHelpers.load_eval_set(eval_set_path)
    runtime = await factory.new_runtime("test", "test-runtime-id")
    runtime_schema = await runtime.get_schema()
    evaluators = await EvalHelpers.load_evaluators(
        eval_set_path, evaluation_set, agent_model=None
    )

    context = UiPathEvalContext()
    context.execution_id = str(uuid.uuid4())
    context.evaluation_set = evaluation_set
    context.runtime_schema = runtime_schema
    context.evaluators = evaluators

    await evaluate(factory, trace_manager, context, event_bus)
    await event_bus.wait_for_all()
    return captured


async def test_user_error_execution_is_not_a_runtime_exception():
    """A USER-category failure is reported unwrapped with runtime_exception=False."""
    error = UiPathRuntimeError(
        UiPathErrorCode.INPUT_INVALID_JSON,
        "Invalid input",
        "Input does not match the expected schema",
        UiPathErrorCategory.USER,
        include_traceback=False,
    )
    events = await _run_failing_eval(error)

    failed = [e for e in events if not e.success]
    assert failed
    details = failed[0].exception_details
    assert details is not None
    assert details.exception is error
    assert details.runtime_exception is False


async def test_unexpected_error_execution_is_a_runtime_exception():
    """A non-user failure in the execution path is flagged as a runtime exception."""
    events = await _run_failing_eval(RuntimeError("infrastructure broke"))

    failed = [e for e in events if not e.success]
    assert failed
    details = failed[0].exception_details
    assert details is not None
    assert isinstance(details.exception, RuntimeError)
    assert details.runtime_exception is True
