"""Tests for the `aggregators` config attached to ExactMatch evaluators.

The aggregator does not run in the Python runtime; the evaluators just embed
its config into per-datapoint justifications so the downstream backend (the
C# layer in Studio Web) can build a confusion matrix + precision/recall/F1
across the dataset. These tests pin the wire shape the backend reads.
"""

import json
import uuid
from typing import Any

import pytest

from uipath.eval.evaluators._aggregators import ClassificationAggregatorSpec
from uipath.eval.evaluators.base_legacy_evaluator import LegacyEvaluationCriteria
from uipath.eval.evaluators.exact_match_evaluator import (
    ExactMatchEvaluator,
    ExactMatchJustification,
)
from uipath.eval.evaluators.legacy_exact_match_evaluator import (
    LegacyExactMatchEvaluator,
)
from uipath.eval.evaluators.output_evaluator import OutputEvaluationCriteria
from uipath.eval.models import BooleanEvaluationResult, NumericEvaluationResult
from uipath.eval.models.models import (
    AgentExecution,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)

CLASSES = ["book", "cancel", "reschedule"]


def _build_exact_match_with_aggregators() -> ExactMatchEvaluator:
    config = {
        "name": "ExactMatchWithClassification",
        "target_output_key": "intent",
        "case_sensitive": False,
        "aggregators": [{"name": "classification", "classes": CLASSES}],
    }
    return ExactMatchEvaluator.model_validate(
        {"evaluatorConfig": config, "id": str(uuid.uuid4())}
    )


def _build_exact_match_no_aggregators() -> ExactMatchEvaluator:
    config = {
        "name": "ExactMatchNoAggregators",
        "target_output_key": "intent",
        "case_sensitive": False,
    }
    return ExactMatchEvaluator.model_validate(
        {"evaluatorConfig": config, "id": str(uuid.uuid4())}
    )


def _legacy_params(
    aggregators: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "id": "test-legacy-exact-match",
        "category": LegacyEvaluatorCategory.Deterministic,
        "type": LegacyEvaluatorType.Equals,
        "name": "ExactMatch",
        "description": "Test legacy exact match with aggregators",
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-01T00:00:00Z",
        "targetOutputKey": "intent",
    }
    if aggregators is not None:
        params["aggregators"] = aggregators
    return params


def _book_intent_execution() -> AgentExecution:
    return AgentExecution(
        agent_input={"utterance": "I want to book a table"},
        agent_output={"intent": "book"},
        agent_trace=[],
    )


class TestExactMatchAggregatorsJustification:
    """ExactMatchEvaluator embeds the aggregator config into the per-datapoint justification."""

    @pytest.mark.asyncio
    async def test_justification_carries_aggregators_back(self) -> None:
        evaluator = _build_exact_match_with_aggregators()
        criteria = OutputEvaluationCriteria(expected_output={"intent": "book"})  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(_book_intent_execution(), criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0
        assert isinstance(result.details, ExactMatchJustification)
        assert result.details.aggregators is not None
        assert len(result.details.aggregators) == 1
        spec = result.details.aggregators[0]
        assert isinstance(spec, ClassificationAggregatorSpec)
        assert spec.name == "classification"
        assert spec.classes == CLASSES

    @pytest.mark.asyncio
    async def test_wire_payload_round_trip(self) -> None:
        """The justification must survive json.dumps(model_dump(by_alias=True))."""
        evaluator = _build_exact_match_with_aggregators()
        criteria = OutputEvaluationCriteria(expected_output={"intent": "book"})  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(_book_intent_execution(), criteria)
        assert isinstance(result.details, ExactMatchJustification)

        wire_string = json.dumps(result.details.model_dump(by_alias=True))
        decoded = json.loads(wire_string)
        assert decoded["aggregators"] == [
            {"name": "classification", "classes": CLASSES}
        ]
        # expected / actual ride along (this is the standard ExactMatch contract).
        assert "expected" in decoded
        assert "actual" in decoded

    @pytest.mark.asyncio
    async def test_justification_omits_aggregators_when_unset(self) -> None:
        evaluator = _build_exact_match_no_aggregators()
        criteria = OutputEvaluationCriteria(expected_output={"intent": "book"})  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(_book_intent_execution(), criteria)
        assert isinstance(result.details, ExactMatchJustification)
        assert result.details.aggregators is None

        # exclude_none must drop the field — keeps the wire payload small/stable.
        dumped = result.details.model_dump(by_alias=True, exclude_none=True)
        assert "aggregators" not in dumped


class TestLegacyExactMatchAggregators:
    """LegacyExactMatch emits JSON-string `details` carrying the aggregator config."""

    @pytest.mark.asyncio
    async def test_legacy_details_is_json_string_when_aggregators_configured(
        self,
    ) -> None:
        evaluator = LegacyExactMatchEvaluator(
            **_legacy_params(
                aggregators=[{"name": "classification", "classes": CLASSES}]
            )
        )
        result = await evaluator.evaluate(
            _book_intent_execution(),
            LegacyEvaluationCriteria(
                expected_output={"intent": "book"}, expected_agent_behavior=""
            ),
        )

        assert isinstance(result, BooleanEvaluationResult)
        assert result.score is True
        assert isinstance(result.details, str)
        decoded = json.loads(result.details)
        assert decoded["aggregators"] == [
            {"name": "classification", "classes": CLASSES}
        ]
        assert "expected" in decoded
        assert "actual" in decoded

    @pytest.mark.asyncio
    async def test_legacy_details_none_when_no_aggregators(self) -> None:
        evaluator = LegacyExactMatchEvaluator(**_legacy_params())
        result = await evaluator.evaluate(
            _book_intent_execution(),
            LegacyEvaluationCriteria(
                expected_output={"intent": "book"}, expected_agent_behavior=""
            ),
        )

        assert isinstance(result, BooleanEvaluationResult)
        assert result.score is True
        assert result.details is None


class TestAggregatorSpecRoundTrip:
    """The ClassificationAggregatorSpec itself round-trips cleanly across JSON."""

    def test_camel_case_alias(self) -> None:
        spec = ClassificationAggregatorSpec(name="classification", classes=["a", "b"])
        wire = spec.model_dump(by_alias=True)
        assert wire == {"name": "classification", "classes": ["a", "b"]}

    def test_validate_from_dict(self) -> None:
        spec = ClassificationAggregatorSpec.model_validate(
            {"name": "classification", "classes": ["yes", "no"]}
        )
        assert spec.classes == ["yes", "no"]
