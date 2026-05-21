"""Tests for the pure-metadata ClassifierEvaluator.

This evaluator carries a `classes` list to downstream consumers (the C# layer
in Studio Web). Its per-datapoint evaluate is a no-op that emits the classes
list as a justification payload. The tests below pin that contract.
"""

import json

import pytest

from uipath.eval.evaluators import (
    ClassifierEvaluator,
    ClassifierJustification,
)
from uipath.eval.evaluators.base_evaluator import BaseEvaluationCriteria
from uipath.eval.evaluators.evaluator_factory import EvaluatorFactory
from uipath.eval.models import AgentExecution, EvaluatorType, NumericEvaluationResult
from uipath.eval.models.models import UiPathEvaluationError


def _build_evaluator(
    classes: list[str] | None = None, source_evaluator: str = "intent_match"
) -> ClassifierEvaluator:
    # Construct via the factory to match how real eval-set runs build evaluators.
    data = {
        "version": "1.0",
        "id": "intent_classifier",
        "name": "intent_classifier",
        "evaluatorTypeId": EvaluatorType.CLASSIFIER.value,
        "evaluatorConfig": {
            "name": "intent_classifier",
            "classes": classes
            if classes is not None
            else ["book", "cancel", "reschedule"],
            "sourceEvaluator": source_evaluator,
        },
    }
    evaluator = EvaluatorFactory.create_evaluator(data)
    assert isinstance(evaluator, ClassifierEvaluator)
    return evaluator


def _agent_execution(output: dict[str, str] | str | None = None) -> AgentExecution:
    return AgentExecution(
        agent_input={"text": "hello"},
        agent_output=output if output is not None else {"intent": "book"},
        agent_trace=[],
    )


class TestClassifierEvaluator:
    async def test_evaluate_returns_zero_score_with_classifier_justification(
        self,
    ) -> None:
        evaluator = _build_evaluator()
        result = await evaluator.evaluate(_agent_execution(), BaseEvaluationCriteria())

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.0
        assert isinstance(result.details, ClassifierJustification)
        assert result.details.classes == ["book", "cancel", "reschedule"]
        assert result.details.source_evaluator == "intent_match"
        # expected / actual are not meaningful for this evaluator
        assert result.details.expected == ""
        assert result.details.actual == ""

    async def test_classes_list_is_independent_copy(self) -> None:
        # If a caller mutates the result's classes list, it shouldn't leak into the config.
        evaluator = _build_evaluator(classes=["a", "b"])
        result = await evaluator.evaluate(_agent_execution(), BaseEvaluationCriteria())
        assert isinstance(result.details, ClassifierJustification)
        result.details.classes.append("c")
        assert evaluator.evaluator_config.classes == ["a", "b"]

    async def test_score_is_zero_regardless_of_agent_output(self) -> None:
        evaluator = _build_evaluator()
        for output in (
            None,
            {},
            {"intent": "book"},
            {"intent": "totally-unrelated"},
            "free text output mentioning cancel",
        ):
            result = await evaluator.evaluate(
                _agent_execution(output), BaseEvaluationCriteria()
            )
            assert result.score == 0.0

    async def test_evaluate_does_not_error_on_missing_criteria(self) -> None:
        # The runtime's validate_and_evaluate_criteria falls back to
        # default_evaluation_criteria when None is passed. Confirm the config's
        # default_evaluation_criteria covers that case.
        evaluator = _build_evaluator()
        result = await evaluator.validate_and_evaluate_criteria(
            _agent_execution(), None
        )
        assert result.score == 0.0
        assert isinstance(result.details, ClassifierJustification)
        assert result.details.classes == ["book", "cancel", "reschedule"]


class TestClassifierJustificationWireShape:
    """Pin the JSON shape that flows from CLI → C# via _serialize_justification."""

    async def test_model_dump_carries_all_config_metadata(self) -> None:
        evaluator = _build_evaluator()
        result = await evaluator.evaluate(_agent_execution(), BaseEvaluationCriteria())
        assert isinstance(result.details, ClassifierJustification)

        dumped = result.details.model_dump()
        # The CLI ships this via json.dumps(model_dump()) — the resulting string
        # is what lands in CodedEvaluatorScore.Justification in the backend.
        wire = json.loads(json.dumps(dumped))
        assert wire["classes"] == ["book", "cancel", "reschedule"]
        assert wire["source_evaluator"] == "intent_match"
        assert wire["expected"] == ""
        assert wire["actual"] == ""

    async def test_wire_payload_can_be_round_tripped_back_to_model(self) -> None:
        evaluator = _build_evaluator()
        result = await evaluator.evaluate(_agent_execution(), BaseEvaluationCriteria())
        assert isinstance(result.details, ClassifierJustification)

        wire_string = json.dumps(result.details.model_dump())
        parsed = ClassifierJustification.model_validate_json(wire_string)
        assert parsed.classes == ["book", "cancel", "reschedule"]
        assert parsed.source_evaluator == "intent_match"


class TestFactoryIntegration:
    def test_factory_builds_classifier_from_v1_config(self) -> None:
        data = {
            "version": "1.0",
            "id": "intent_classifier",
            "name": "intent_classifier",
            "evaluatorTypeId": EvaluatorType.CLASSIFIER.value,
            "evaluatorConfig": {
                "name": "intent_classifier",
                "classes": ["book", "cancel", "reschedule"],
                "sourceEvaluator": "intent_match",
            },
        }
        evaluator = EvaluatorFactory.create_evaluator(data)
        assert isinstance(evaluator, ClassifierEvaluator)
        assert evaluator.evaluator_config.classes == ["book", "cancel", "reschedule"]
        assert evaluator.evaluator_config.source_evaluator == "intent_match"
        assert evaluator.id == "intent_classifier"

    def test_factory_accepts_snake_case_aliases(self) -> None:
        data = {
            "version": "1.0",
            "id": "intent_classifier",
            "name": "intent_classifier",
            "evaluatorTypeId": EvaluatorType.CLASSIFIER.value,
            "evaluatorConfig": {
                "name": "intent_classifier",
                "classes": ["yes", "no"],
                "source_evaluator": "yes_no_match",
            },
        }
        evaluator = EvaluatorFactory.create_evaluator(data)
        assert isinstance(evaluator, ClassifierEvaluator)
        assert evaluator.evaluator_config.source_evaluator == "yes_no_match"

    def test_factory_rejects_config_missing_classes(self) -> None:
        data = {
            "version": "1.0",
            "id": "intent_classifier",
            "name": "intent_classifier",
            "evaluatorTypeId": EvaluatorType.CLASSIFIER.value,
            "evaluatorConfig": {
                "name": "intent_classifier",
                "sourceEvaluator": "intent_match",
                # classes missing
            },
        }
        with pytest.raises(UiPathEvaluationError):
            EvaluatorFactory.create_evaluator(data)
