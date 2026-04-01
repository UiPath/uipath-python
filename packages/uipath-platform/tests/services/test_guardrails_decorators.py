"""Tests for the guardrails decorator framework in uipath-platform.

Focus: meaningful business behaviour — serialization, PRE/POST evaluation,
modification flow, stage enforcement, factory-function path, and integration
scenarios modelled on the joke-agent-decorator sample.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Annotated, Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel
from uipath.core.guardrails import (
    GuardrailValidationResult,
    GuardrailValidationResultType,
)

from uipath.platform.guardrails.decorators import (
    BlockAction,
    CustomValidator,
    GuardrailAction,
    GuardrailBlockException,
    GuardrailExclude,
    GuardrailExecutionStage,
    LogAction,
    LoggingSeverityLevel,
    PIIDetectionEntity,
    PIIDetectionEntityType,
    PIIValidator,
    PromptInjectionValidator,
    guardrail,
    register_guardrail_adapter,
)
from uipath.platform.guardrails.decorators._core import (
    _collect_output,
    _get_excluded_params,
    _make_evaluator,
    _reconstruct_output,
    _serialize_value,
)
from uipath.platform.guardrails.decorators._registry import (
    _adapters,
)

# ---------------------------------------------------------------------------
# Shared result constants
# ---------------------------------------------------------------------------

_PASSED = GuardrailValidationResult(
    result=GuardrailValidationResultType.PASSED,
    reason="ok",
)
_FAILED = GuardrailValidationResult(
    result=GuardrailValidationResultType.VALIDATION_FAILED,
    reason="violation detected",
)


# ---------------------------------------------------------------------------
# Registry isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_adapter_registry():
    """Snapshot and restore the global adapter registry around every test."""
    snapshot = list(_adapters)
    yield
    _adapters.clear()
    _adapters.extend(snapshot)


# ---------------------------------------------------------------------------
# Minimal fake types for adapter tests (no LangChain dependency)
# ---------------------------------------------------------------------------


class _DummyTarget:
    """Minimal callable target recognised by _DummyAdapter."""

    def __init__(self, return_value: Any = None) -> None:
        self.return_value = (
            return_value if return_value is not None else {"output": "result"}
        )
        self.invoke_calls: list[Any] = []

    def invoke(self, args: Any) -> Any:
        self.invoke_calls.append(args)
        return self.return_value


class _WrappedDummyTarget:
    """A _DummyTarget wrapped with guardrail evaluation."""

    def __init__(
        self,
        target: Any,
        evaluator: Any,
        action: GuardrailAction,
        name: str,
        stage: GuardrailExecutionStage,
    ) -> None:
        self._target = target
        self._evaluator = evaluator
        self._action = action
        self._name = name
        self._stage = stage

    def invoke(self, args: Any) -> Any:
        input_data = args if isinstance(args, dict) else {"input": args}
        if self._stage in (
            GuardrailExecutionStage.PRE,
            GuardrailExecutionStage.PRE_AND_POST,
        ):
            result = self._evaluator(
                input_data, GuardrailExecutionStage.PRE, input_data, None
            )
            if result.result == GuardrailValidationResultType.VALIDATION_FAILED:
                self._action.handle_validation_result(result, input_data, self._name)
        raw = self._target.invoke(args)
        output_data = raw if isinstance(raw, dict) else {"output": raw}
        if self._stage in (
            GuardrailExecutionStage.POST,
            GuardrailExecutionStage.PRE_AND_POST,
        ):
            result = self._evaluator(
                output_data, GuardrailExecutionStage.POST, input_data, output_data
            )
            if result.result == GuardrailValidationResultType.VALIDATION_FAILED:
                self._action.handle_validation_result(result, output_data, self._name)
        return raw


class _DummyAdapter:
    """Adapter that handles _DummyTarget and _WrappedDummyTarget instances."""

    def recognize(self, target: Any) -> bool:
        return isinstance(target, (_DummyTarget, _WrappedDummyTarget))

    def wrap(
        self,
        target: Any,
        evaluator: Any,
        action: GuardrailAction,
        name: str,
        stage: GuardrailExecutionStage,
    ) -> Any:
        return _WrappedDummyTarget(target, evaluator, action, name, stage)


# ---------------------------------------------------------------------------
# 1. PIIDetectionEntity — threshold boundary enforcement
# ---------------------------------------------------------------------------


class TestPIIDetectionEntity:
    def test_threshold_below_zero_raises(self):
        with pytest.raises(ValueError, match="0.0 and 1.0"):
            PIIDetectionEntity(name="Email", threshold=-0.1)

    def test_threshold_above_one_raises(self):
        with pytest.raises(ValueError, match="0.0 and 1.0"):
            PIIDetectionEntity(name="Email", threshold=1.1)


# ---------------------------------------------------------------------------
# 2. LogAction — does NOT stop execution; uses configured severity
# ---------------------------------------------------------------------------


class TestLogAction:
    def test_violation_logs_guardrail_name_and_execution_continues(self, caplog):
        action = LogAction()
        with caplog.at_level(logging.WARNING):
            result = action.handle_validation_result(_FAILED, "data", "MyGuardrail")
        assert result is None  # execution continues
        assert any("MyGuardrail" in r.message for r in caplog.records)

    def test_pass_emits_no_log(self, caplog):
        action = LogAction()
        with caplog.at_level(logging.WARNING):
            action.handle_validation_result(_PASSED, "data", "G")
        assert not caplog.records

    def test_custom_message_overrides_reason(self, caplog):
        action = LogAction(message="custom alert")
        with caplog.at_level(logging.WARNING):
            action.handle_validation_result(_FAILED, "data", "G")
        assert any("custom alert" in r.message for r in caplog.records)

    def test_default_message_includes_validation_reason(self, caplog):
        action = LogAction()
        with caplog.at_level(logging.WARNING):
            action.handle_validation_result(_FAILED, "data", "G")
        assert any("violation detected" in r.message for r in caplog.records)

    def test_debug_severity(self, caplog):
        action = LogAction(severity_level=LoggingSeverityLevel.DEBUG)
        with caplog.at_level(logging.DEBUG):
            action.handle_validation_result(_FAILED, "data", "G")
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert debug_records


# ---------------------------------------------------------------------------
# 3. BlockAction — raises GuardrailBlockException on violation
# ---------------------------------------------------------------------------


class TestBlockAction:
    def test_raises_on_violation(self):
        action = BlockAction()
        with pytest.raises(GuardrailBlockException):
            action.handle_validation_result(_FAILED, "data", "G")

    def test_no_raise_on_pass(self):
        action = BlockAction()
        result = action.handle_validation_result(_PASSED, "data", "G")
        assert result is None

    def test_title_and_detail_from_result(self):
        action = BlockAction()
        with pytest.raises(GuardrailBlockException) as exc_info:
            action.handle_validation_result(_FAILED, "data", "MyGuardrail")
        assert exc_info.value.title
        assert exc_info.value.detail

    def test_custom_title_and_detail(self):
        action = BlockAction(title="Blocked", detail="Not allowed")
        with pytest.raises(GuardrailBlockException) as exc_info:
            action.handle_validation_result(_FAILED, "data", "G")
        assert exc_info.value.title == "Blocked"
        assert exc_info.value.detail == "Not allowed"


# ---------------------------------------------------------------------------
# 4. PIIValidator — builds correct BuiltInValidatorGuardrail
# ---------------------------------------------------------------------------


class TestPIIValidator:
    def test_empty_entities_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            PIIValidator(entities=[])

    def test_entity_names_and_thresholds_in_api_parameters(self):
        v = PIIValidator(
            entities=[
                PIIDetectionEntity(PIIDetectionEntityType.EMAIL, 0.6),
                PIIDetectionEntity(PIIDetectionEntityType.PERSON, 0.8),
            ]
        )
        g = v.get_built_in_guardrail("G", None, True)
        param_by_id = {p.id: p for p in g.validator_parameters}
        entities_value = param_by_id["entities"].value
        assert isinstance(entities_value, list)
        assert "Email" in entities_value
        assert "Person" in entities_value
        thresholds_value = param_by_id["entityThresholds"].value
        assert isinstance(thresholds_value, dict)
        assert thresholds_value["Email"] == 0.6
        assert thresholds_value["Person"] == 0.8

    def test_no_scope_restriction(self):
        v = PIIValidator(entities=[PIIDetectionEntity(PIIDetectionEntityType.EMAIL)])
        # All stages allowed — no ValueError raised
        v.validate_stage(GuardrailExecutionStage.PRE)
        v.validate_stage(GuardrailExecutionStage.POST)

    def test_selector_is_none(self):
        v = PIIValidator(entities=[PIIDetectionEntity(PIIDetectionEntityType.EMAIL)])
        g = v.get_built_in_guardrail("G", None, True)
        assert g.selector is None


# ---------------------------------------------------------------------------
# 5. PromptInjectionValidator — LLM-only, PRE-only, threshold validation
# ---------------------------------------------------------------------------


class TestPromptInjectionValidator:
    def test_threshold_below_zero_raises(self):
        with pytest.raises(ValueError, match="threshold"):
            PromptInjectionValidator(threshold=-0.1)

    def test_threshold_above_one_raises(self):
        with pytest.raises(ValueError, match="threshold"):
            PromptInjectionValidator(threshold=1.1)

    def test_restricted_to_pre_stage_only(self):
        v = PromptInjectionValidator()
        v.validate_stage(GuardrailExecutionStage.PRE)  # ok
        with pytest.raises(ValueError):
            v.validate_stage(GuardrailExecutionStage.POST)

    def test_builds_prompt_injection_guardrail_with_threshold(self):
        v = PromptInjectionValidator(threshold=0.7)
        g = v.get_built_in_guardrail("PI", None, True)
        assert g.validator_type == "prompt_injection"
        threshold_param = next(p for p in g.validator_parameters if p.id == "threshold")
        assert threshold_param.value == 0.7

    def test_selector_is_none(self):
        v = PromptInjectionValidator()
        g = v.get_built_in_guardrail("PI", None, True)
        assert g.selector is None


# ---------------------------------------------------------------------------
# 6. CustomValidator — rule routing and error handling
# ---------------------------------------------------------------------------


class TestCustomValidator:
    def test_non_callable_raises(self):
        with pytest.raises(ValueError, match="callable"):
            CustomValidator(rule="not_a_function")  # type: ignore[arg-type]

    def test_wrong_arity_raises(self):
        with pytest.raises(ValueError, match="1 or 2"):
            CustomValidator(rule=lambda: True)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="1 or 2"):
            CustomValidator(rule=lambda a, b, c: True)  # type: ignore[arg-type]

    def test_one_param_pre_receives_input_data(self):
        received: list[Any] = []

        def capture_pre(args: dict[str, Any]) -> bool:
            received.append(args)
            return False

        CustomValidator(rule=capture_pre).evaluate(
            {}, GuardrailExecutionStage.PRE, {"a": 1}, None
        )
        assert received == [{"a": 1}]

    def test_one_param_post_receives_output_data(self):
        received: list[Any] = []

        def capture_post(args: dict[str, Any]) -> bool:
            received.append(args)
            return False

        CustomValidator(rule=capture_post).evaluate(
            {}, GuardrailExecutionStage.POST, {"in": 1}, {"out": 2}
        )
        assert received == [{"out": 2}]

    def test_two_param_post_receives_input_and_output(self):
        received: list[Any] = []

        def rule(inp: dict[str, Any], out: dict[str, Any]) -> bool:
            received.append((inp, out))
            return False

        CustomValidator(rule=rule).evaluate(
            {}, GuardrailExecutionStage.POST, {"in": 1}, {"out": 2}
        )
        assert received == [({"in": 1}, {"out": 2})]

    def test_two_param_rule_skipped_when_input_missing(self):
        result = CustomValidator(rule=lambda a, b: True).evaluate(
            {}, GuardrailExecutionStage.POST, None, {"out": 2}
        )
        assert result.result == GuardrailValidationResultType.PASSED

    def test_rule_returning_true_means_violation(self):
        result = CustomValidator(rule=lambda args: True).evaluate(
            {}, GuardrailExecutionStage.PRE, {"x": 1}, None
        )
        assert result.result == GuardrailValidationResultType.VALIDATION_FAILED

    def test_rule_exception_returns_passed(self):
        def bad(args: dict[str, Any]) -> bool:
            raise ValueError("boom")

        result = CustomValidator(rule=bad).evaluate(
            {}, GuardrailExecutionStage.PRE, {"x": 1}, None
        )
        assert result.result == GuardrailValidationResultType.PASSED


# ---------------------------------------------------------------------------
# 7. GuardrailExclude — parameter introspection
# ---------------------------------------------------------------------------


class TestGuardrailExclude:
    def test_excluded_param_not_in_collected_input(self):
        def func(
            text: str,
            config: Annotated[dict[str, Any], GuardrailExclude()],
        ) -> str:
            return text

        excluded = _get_excluded_params(func)
        assert "config" in excluded
        assert "text" not in excluded

    def test_multiple_excluded_params(self):
        def func(
            a: str,
            b: Annotated[int, GuardrailExclude()],
            c: Annotated[str, GuardrailExclude()],
        ) -> str:
            return a

        excluded = _get_excluded_params(func)
        assert excluded == {"b", "c"}

    def test_no_annotations_returns_empty_set(self):
        def func(a: str, b: int) -> str:
            return a

        assert _get_excluded_params(func) == set()


# ---------------------------------------------------------------------------
# 8. Serialization helpers
# ---------------------------------------------------------------------------


class _PydanticModel(BaseModel):
    topic: str
    count: int = 0


@dataclasses.dataclass
class _Dataclass:
    name: str
    value: float


class TestSerializationHelpers:
    def test_primitive_str_passthrough(self):
        assert _serialize_value("hello") == "hello"

    def test_primitive_int_passthrough(self):
        assert _serialize_value(42) == 42

    def test_dict_passthrough(self):
        assert _serialize_value({"a": 1}) == {"a": 1}

    def test_pydantic_model_dumps(self):
        m = _PydanticModel(topic="test", count=3)
        result = _serialize_value(m)
        assert result == {"topic": "test", "count": 3}

    def test_dataclass_asdict(self):
        d = _Dataclass(name="x", value=1.5)
        result = _serialize_value(d)
        assert result == {"name": "x", "value": 1.5}

    def test_collect_output_from_pydantic(self):
        m = _PydanticModel(topic="joke")
        result = _collect_output(m)
        assert result == {"topic": "joke", "count": 0}

    def test_collect_output_from_str(self):
        result = _collect_output("hello")
        assert result == {"return": "hello"}

    def test_collect_output_from_dict(self):
        result = _collect_output({"key": "val"})
        assert result == {"key": "val"}

    def test_reconstruct_output_pydantic(self):
        original = _PydanticModel(topic="original")
        modified = {"topic": "modified", "count": 5}
        result = _reconstruct_output(original, modified)
        assert isinstance(result, _PydanticModel)
        assert result.topic == "modified"
        assert result.count == 5

    def test_reconstruct_output_str(self):
        result = _reconstruct_output("original", "modified")
        assert result == "modified"

    def test_reconstruct_output_none_returns_original(self):
        result = _reconstruct_output("original", None)
        assert result == "original"


# ---------------------------------------------------------------------------
# 9. @guardrail on sync functions
# ---------------------------------------------------------------------------


class TestGuardrailOnSyncFunction:
    def test_pre_fires_before_function(self):
        calls: list[str] = []

        mock_validator = MagicMock()
        mock_validator.supported_stages = []
        mock_validator.validate_stage = MagicMock()

        mock_validator.run.side_effect = lambda *a, **kw: (
            calls.append("eval") or _PASSED  # type: ignore[func-returns-value]
        )

        @guardrail(
            validator=mock_validator,
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        def fn(text: str) -> str:
            calls.append("fn")
            return text

        fn("hello")
        assert calls == ["eval", "fn"]

    def test_post_fires_after_function(self):
        calls: list[str] = []

        mock_validator = MagicMock()
        mock_validator.supported_stages = []
        mock_validator.validate_stage = MagicMock()

        mock_validator.run.side_effect = lambda *a, **kw: (
            calls.append("eval") or _PASSED  # type: ignore[func-returns-value]
        )

        @guardrail(
            validator=mock_validator,
            action=LogAction(),
            stage=GuardrailExecutionStage.POST,
        )
        def fn(text: str) -> str:
            calls.append("fn")
            return text

        fn("hello")
        assert calls == ["fn", "eval"]

    def test_block_action_raises_guardrail_block_exception(self):
        mock_validator = MagicMock()
        mock_validator.supported_stages = []
        mock_validator.validate_stage = MagicMock()

        mock_validator.run.return_value = _FAILED

        @guardrail(
            validator=mock_validator,
            action=BlockAction(title="Blocked", detail="not allowed"),
            stage=GuardrailExecutionStage.PRE,
        )
        def fn(text: str) -> str:
            return text

        with pytest.raises(GuardrailBlockException):
            fn("bad input")

    def test_log_action_does_not_stop_execution(self):
        mock_validator = MagicMock()
        mock_validator.supported_stages = []
        mock_validator.validate_stage = MagicMock()

        mock_validator.run.return_value = _FAILED

        result = []

        @guardrail(
            validator=mock_validator,
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        def fn(text: str) -> str:
            result.append("called")
            return text

        fn("input")
        assert result == ["called"]

    def test_pre_input_contains_function_params(self):
        captured: list[Any] = []

        @guardrail(
            validator=CustomValidator(
                lambda args: captured.append(args) or False  # type: ignore[func-returns-value]
            ),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        def fn(joke: str, count: int) -> str:
            return joke

        fn("why did the chicken", 3)
        assert captured == [{"joke": "why did the chicken", "count": 3}]

    def test_excluded_param_absent_from_pre_input(self):
        captured: list[Any] = []

        @guardrail(
            validator=CustomValidator(
                lambda args: captured.append(args) or False  # type: ignore[func-returns-value]
            ),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        def fn(
            joke: str,
            config: Annotated[dict[str, Any], GuardrailExclude()],
        ) -> str:
            return joke

        fn("why did the chicken", {"debug": True})
        assert "config" not in captured[0]
        assert "joke" in captured[0]

    def test_pre_modification_updates_function_args(self):
        class _ReplaceAction(GuardrailAction):
            def handle_validation_result(self, result, data, name):
                if isinstance(data, dict) and "joke" in data:
                    return {"joke": data["joke"].replace("donkey", "[censored]")}
                return data

        @guardrail(
            validator=CustomValidator(lambda args: "donkey" in args.get("joke", "")),
            action=_ReplaceAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        def fn(joke: str) -> str:
            return joke

        result = fn("why did the donkey cross the road")
        assert result == "why did the [censored] cross the road"

    def test_post_output_contains_return_value(self):
        captured: list[Any] = []

        @guardrail(
            validator=CustomValidator(
                lambda args: captured.append(args) or False  # type: ignore[func-returns-value]
            ),
            action=LogAction(),
            stage=GuardrailExecutionStage.POST,
        )
        def fn(x: int) -> dict[str, int]:
            return {"result": x * 2}

        fn(5)
        assert captured == [{"result": 10}]

    def test_post_modification_updates_return_value(self):
        class _FixedAction(GuardrailAction):
            def handle_validation_result(self, result, data, name):
                return {"result": 99}

        @guardrail(
            validator=CustomValidator(lambda args: True),
            action=_FixedAction(),
            stage=GuardrailExecutionStage.POST,
        )
        def fn(x: int) -> dict[str, int]:
            return {"result": x * 2}

        assert fn(5) == {"result": 99}

    def test_pre_and_post_both_fire(self):
        calls: list[str] = []

        mock_validator = MagicMock()
        mock_validator.supported_stages = []
        mock_validator.validate_stage = MagicMock()

        mock_validator.run.side_effect = lambda name, desc, enabled, data, stage, *a: (
            calls.append(stage.value) or _PASSED  # type: ignore[func-returns-value]
        )

        @guardrail(
            validator=mock_validator,
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE_AND_POST,
        )
        def fn(x: int) -> int:
            return x + 1

        fn(1)
        assert "pre" in calls
        assert "post" in calls


# ---------------------------------------------------------------------------
# 10. @guardrail on async functions
# ---------------------------------------------------------------------------


class TestGuardrailOnAsyncFunction:
    @pytest.mark.asyncio
    async def test_pre_fires_before_async_function(self):
        calls: list[str] = []

        mock_validator = MagicMock()
        mock_validator.supported_stages = []
        mock_validator.validate_stage = MagicMock()

        mock_validator.run.side_effect = lambda *a, **kw: (
            calls.append("eval") or _PASSED  # type: ignore[func-returns-value]
        )

        @guardrail(
            validator=mock_validator,
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        async def fn(text: str) -> str:
            calls.append("fn")
            return text

        await fn("hello")
        assert calls == ["eval", "fn"]

    @pytest.mark.asyncio
    async def test_block_action_raises_in_async(self):
        mock_validator = MagicMock()
        mock_validator.supported_stages = []
        mock_validator.validate_stage = MagicMock()

        mock_validator.run.return_value = _FAILED

        @guardrail(
            validator=mock_validator,
            action=BlockAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        async def fn(text: str) -> str:
            return text

        with pytest.raises(GuardrailBlockException):
            await fn("bad")

    @pytest.mark.asyncio
    async def test_post_modification_in_async(self):
        class _FortyTwoAction(GuardrailAction):
            def handle_validation_result(self, result, data, name):
                return {"result": 42}

        @guardrail(
            validator=CustomValidator(lambda args: True),
            action=_FortyTwoAction(),
            stage=GuardrailExecutionStage.POST,
        )
        async def fn(x: int) -> dict[str, int]:
            return {"result": x}

        assert await fn(1) == {"result": 42}


# ---------------------------------------------------------------------------
# 11. Stage enforcement at decoration time
# ---------------------------------------------------------------------------


class TestStageEnforcement:
    def test_prompt_injection_on_post_raises_at_decoration(self):
        with pytest.raises(ValueError, match="stage"):
            guardrail(
                lambda text: text,
                validator=PromptInjectionValidator(),
                action=LogAction(),
                stage=GuardrailExecutionStage.POST,
            )

    def test_prompt_injection_on_pre_and_post_raises_at_decoration(self):
        with pytest.raises(ValueError, match="stage"):
            guardrail(
                lambda text: text,
                validator=PromptInjectionValidator(),
                action=LogAction(),
                stage=GuardrailExecutionStage.PRE_AND_POST,
            )

    def test_prompt_injection_on_pre_ok(self):
        # Should not raise
        guardrail(
            lambda text: text,
            validator=PromptInjectionValidator(),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )


# ---------------------------------------------------------------------------
# 12. @guardrail validation (bad arguments)
# ---------------------------------------------------------------------------


class TestGuardrailDecorator:
    def test_missing_action_raises(self):
        with pytest.raises(ValueError, match="action must be provided"):
            guardrail(
                lambda text: text,
                validator=CustomValidator(lambda args: False),
                action=None,  # type: ignore[arg-type]
            )

    def test_non_action_instance_raises(self):
        with pytest.raises(ValueError, match="GuardrailAction"):
            guardrail(
                lambda text: text,
                validator=CustomValidator(lambda args: False),
                action="bad",  # type: ignore[arg-type]
            )

    def test_invalid_enabled_for_evals_type_raises(self):
        with pytest.raises(ValueError, match="boolean"):
            guardrail(
                lambda text: text,
                validator=CustomValidator(lambda args: False),
                action=LogAction(),
                enabled_for_evals="yes",  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# 13. Stacked decorators
# ---------------------------------------------------------------------------


class TestStackedDecorators:
    def test_both_decorators_fire_on_same_function(self):
        calls: list[str] = []

        def _make_mock(tag: str) -> Any:
            m = MagicMock()
            m.supported_stages = []
            m.validate_stage = MagicMock()
            m.get_built_in_guardrail.return_value = None
            m.run.side_effect = lambda *a, **kw: calls.append(tag) or _PASSED  # type: ignore[func-returns-value]
            return m

        @guardrail(
            validator=_make_mock("outer"),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
            name="outer",
        )
        @guardrail(
            validator=_make_mock("inner"),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
            name="inner",
        )
        def fn(text: str) -> str:
            return text

        fn("hello")
        assert "outer" in calls
        assert "inner" in calls

    def test_outer_block_prevents_inner_from_firing(self):
        inner_called = []

        outer_validator = MagicMock()
        outer_validator.supported_stages = []
        outer_validator.validate_stage = MagicMock()
        outer_validator.get_built_in_guardrail.return_value = None
        outer_validator.run.return_value = _FAILED

        inner_validator = MagicMock()
        inner_validator.supported_stages = []
        inner_validator.validate_stage = MagicMock()
        inner_validator.get_built_in_guardrail.return_value = None
        inner_validator.run.side_effect = lambda *a, **kw: (
            inner_called.append(True) or _PASSED  # type: ignore[func-returns-value]
        )

        @guardrail(
            validator=outer_validator,
            action=BlockAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        @guardrail(
            validator=inner_validator,
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        def fn(text: str) -> str:
            return text

        with pytest.raises(GuardrailBlockException):
            fn("bad")

        assert not inner_called


# ---------------------------------------------------------------------------
# 14. Factory function path (adapter wraps return value)
# ---------------------------------------------------------------------------


class TestFactoryFunctionPath:
    def test_adapter_wraps_return_value_of_factory(self):
        register_guardrail_adapter(_DummyAdapter())
        target = _DummyTarget(return_value={"output": "ok"})

        @guardrail(
            validator=CustomValidator(lambda args: False),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        def factory() -> _DummyTarget:
            return target

        wrapped = factory()
        assert isinstance(wrapped, _WrappedDummyTarget)

    def test_factory_pre_guardrail_fires_on_factory_params(self):
        register_guardrail_adapter(_DummyAdapter())
        captured: list[Any] = []
        target = _DummyTarget()

        @guardrail(
            validator=CustomValidator(
                lambda args: captured.append(args) or False  # type: ignore[func-returns-value]
            ),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        def factory(config: str) -> _DummyTarget:
            return target

        factory("test-config")
        assert captured == [{"config": "test-config"}]

    def test_adapter_recognizes_direct_object(self):
        register_guardrail_adapter(_DummyAdapter())
        target = _DummyTarget()

        wrapped = guardrail(
            target,
            validator=CustomValidator(lambda args: False),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        assert isinstance(wrapped, _WrappedDummyTarget)

    def test_stacked_guardrails_on_factory_both_wrap_return_value(self):
        register_guardrail_adapter(_DummyAdapter())
        target = _DummyTarget()
        evals: list[str] = []

        def _make_mock(tag: str) -> Any:
            m = MagicMock()
            m.supported_stages = []
            m.validate_stage = MagicMock()
            m.get_built_in_guardrail.return_value = None
            m.run.side_effect = lambda *a, **kw: evals.append(tag) or _PASSED  # type: ignore[func-returns-value]
            return m

        @guardrail(
            validator=_make_mock("outer"),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        @guardrail(
            validator=_make_mock("inner"),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        def factory() -> _DummyTarget:
            return target

        wrapped = factory()
        wrapped.invoke({"x": 1})
        assert "outer" in evals
        assert "inner" in evals


# ---------------------------------------------------------------------------
# 15. _make_evaluator — local vs API path
# ---------------------------------------------------------------------------


class TestMakeEvaluator:
    def test_custom_validator_path_delegates_to_run(self):
        """_make_evaluator with a CustomGuardrailValidator calls validator.run()."""
        mock_validator = MagicMock()
        mock_validator.run.return_value = _PASSED
        evaluator = _make_evaluator(mock_validator, "G", None, True)
        result = evaluator({"data": 1}, GuardrailExecutionStage.PRE, {"a": 1}, None)
        mock_validator.run.assert_called_once_with(
            "G", None, True, {"data": 1}, GuardrailExecutionStage.PRE, {"a": 1}, None
        )
        assert result == _PASSED

    def test_built_in_validator_path_lazy_initializes_uipath(self):
        """BuiltInGuardrailValidator.run() lazily creates UiPath() and calls API."""
        from uipath.platform.guardrails.decorators.validators import (
            BuiltInGuardrailValidator,
        )
        from uipath.platform.guardrails.guardrails import BuiltInValidatorGuardrail

        mock_built_in = MagicMock(spec=BuiltInValidatorGuardrail)

        class _TestBuiltIn(BuiltInGuardrailValidator):
            def get_built_in_guardrail(self, name, description, enabled_for_evals):
                return mock_built_in

        validator = _TestBuiltIn()
        evaluator = _make_evaluator(validator, "G", None, True)

        mock_uipath = MagicMock()
        mock_uipath.guardrails.evaluate_guardrail.return_value = _PASSED
        with patch("uipath.platform.UiPath", return_value=mock_uipath):
            evaluator({"text": "hello"}, GuardrailExecutionStage.PRE, None, None)
            evaluator({"text": "hello"}, GuardrailExecutionStage.PRE, None, None)

        # UiPath() should be created only once despite two calls
        assert mock_uipath.guardrails.evaluate_guardrail.call_count == 2


# ---------------------------------------------------------------------------
# 16. Joke-agent integration scenarios (plain functions)
# ---------------------------------------------------------------------------


class _JokeInput(BaseModel):
    topic: str


class _JokeOutput(BaseModel):
    joke: str


class TestJokeAgentScenarios:
    """Integration tests modelled on the joke-agent-decorator sample."""

    def test_pii_validator_blocks_person_name_in_topic(self):
        """Agent-level PRE guardrail blocks person names in the input topic."""
        calls: list[str] = []

        mock_validator = MagicMock()
        mock_validator.supported_stages = []
        mock_validator.validate_stage = MagicMock()

        mock_validator.run.return_value = _FAILED

        @guardrail(
            validator=mock_validator,
            action=BlockAction(title="Person detected", detail="Not allowed"),
            stage=GuardrailExecutionStage.PRE,
            name="Agent PII",
        )
        async def joke_node(state: _JokeInput) -> _JokeOutput:
            calls.append("called")
            return _JokeOutput(joke="a joke")

        import asyncio

        with pytest.raises(GuardrailBlockException):
            asyncio.run(joke_node(_JokeInput(topic="John Smith")))
        assert not calls

    def test_input_pydantic_model_serialized_for_guardrail(self):
        """State Pydantic model is serialized to dict and sent to evaluator."""
        captured: list[Any] = []

        @guardrail(
            validator=CustomValidator(
                lambda args: captured.append(args) or False  # type: ignore[func-returns-value]
            ),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        def process(state: _JokeInput) -> _JokeOutput:
            return _JokeOutput(joke="a joke")

        process(_JokeInput(topic="cats"))
        assert captured == [{"state": {"topic": "cats"}}]

    def test_output_pydantic_model_serialized_for_guardrail(self):
        """Return Pydantic model is serialized to dict and sent to POST evaluator."""
        captured: list[Any] = []

        @guardrail(
            validator=CustomValidator(
                lambda args: captured.append(args) or False  # type: ignore[func-returns-value]
            ),
            action=LogAction(),
            stage=GuardrailExecutionStage.POST,
        )
        def process(state: _JokeInput) -> _JokeOutput:
            return _JokeOutput(joke="funny joke about cats")

        process(_JokeInput(topic="cats"))
        assert captured == [{"joke": "funny joke about cats"}]

    def test_excluded_config_param_not_in_guardrail_input(self):
        """RunnableConfig-style param excluded from evaluation."""
        captured: list[Any] = []

        @guardrail(
            validator=CustomValidator(
                lambda args: captured.append(args) or False  # type: ignore[func-returns-value]
            ),
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
        )
        def process(
            state: _JokeInput,
            config: Annotated[dict[str, Any], GuardrailExclude()],
        ) -> _JokeOutput:
            return _JokeOutput(joke="joke")

        process(_JokeInput(topic="dogs"), {"thread_id": "abc"})
        assert "config" not in captured[0]
        assert "state" in captured[0]

    def test_word_filter_custom_validator_on_tool_function(self):
        """CustomValidator on plain function replaces offensive word via action."""
        censored: list[str] = []

        class CensorAction(GuardrailAction):
            def handle_validation_result(self, result, data, name):
                if isinstance(data, dict) and "joke" in data:
                    censored.append(data["joke"])
                    return {"joke": data["joke"].replace("donkey", "[censored]")}
                return data

        @guardrail(
            validator=CustomValidator(
                lambda args: "donkey" in args.get("joke", "").lower()
            ),
            action=CensorAction(),
            stage=GuardrailExecutionStage.PRE,
            name="Word Filter",
        )
        def analyze_joke(joke: str) -> str:
            return f"analyzed: {joke}"

        result = analyze_joke(joke="why did the donkey cross the road")
        assert "censored" in result
        assert "donkey" not in result

    def test_log_action_does_not_stop_joke_generation(self):
        """LogAction on PII violation logs but lets execution continue."""

        @guardrail(
            validator=CustomValidator(lambda args: True),  # always violate
            action=LogAction(),
            stage=GuardrailExecutionStage.PRE,
            name="Always-Log",
        )
        def generate_joke(topic: str) -> str:
            return f"joke about {topic}"

        result = generate_joke("cats")
        assert result == "joke about cats"

    def test_length_limiter_blocks_long_joke(self):
        """BlockAction on length check raises for over-long content."""

        @guardrail(
            validator=CustomValidator(lambda args: len(args.get("joke", "")) > 10),
            action=BlockAction(title="Too long", detail="Joke exceeds limit"),
            stage=GuardrailExecutionStage.PRE,
        )
        def submit_joke(joke: str) -> str:
            return joke

        with pytest.raises(GuardrailBlockException, match="Too long"):
            submit_joke(joke="a" * 20)

        # Short joke passes through
        assert submit_joke(joke="short") == "short"
