"""Unit tests for the StudioWeb eval reporting strategies."""

import uuid

from uipath._cli._evals._reporting import (
    CodedEvalReportingStrategy,
    EvalReportingStrategy,
    LegacyEvalReportingStrategy,
    is_coded_evaluators,
    strategy_for,
)
from uipath.eval.models.evaluation_set import EvaluationItem

LEGACY = LegacyEvalReportingStrategy()
CODED = CodedEvalReportingStrategy()


def _eval_item(criterias) -> EvaluationItem:
    return EvaluationItem(
        **{
            "id": "my-eval-item",
            "name": "Item",
            "inputs": {"a": 1},
            "evaluationCriterias": criterias,
        }
    )


class TestStrategySelection:
    def test_strategy_for_returns_singletons_by_kind(self):
        assert isinstance(strategy_for(True), CodedEvalReportingStrategy)
        assert isinstance(strategy_for(False), LegacyEvalReportingStrategy)

    def test_strategies_satisfy_protocol(self):
        assert isinstance(LEGACY, EvalReportingStrategy)
        assert isinstance(CODED, EvalReportingStrategy)

    def test_is_coded_evaluators_with_empty_list(self):
        assert is_coded_evaluators([]) is False


class TestEndpointSuffix:
    def test_legacy_has_no_suffix(self):
        assert LEGACY.endpoint_suffix == ""

    def test_coded_uses_coded_segment(self):
        assert CODED.endpoint_suffix == "coded/"


class TestConvertId:
    def test_legacy_passes_through_existing_guid(self):
        guid = str(uuid.uuid4())
        assert LEGACY.convert_id(guid) == guid

    def test_legacy_maps_string_to_deterministic_guid(self):
        converted = LEGACY.convert_id("not-a-guid")
        # Valid GUID...
        uuid.UUID(converted)
        # ...and deterministic
        assert converted == LEGACY.convert_id("not-a-guid")
        assert converted == str(uuid.uuid5(uuid.NAMESPACE_DNS, "not-a-guid"))

    def test_coded_passes_strings_through_unchanged(self):
        assert CODED.convert_id("not-a-guid") == "not-a-guid"


class TestEvalSnapshot:
    def test_legacy_extracts_expected_output_from_first_criteria(self):
        item = _eval_item({"Evaluator": {"expectedOutput": {"answer": 42}}})
        snapshot = LEGACY.build_eval_snapshot(item)
        assert snapshot["expectedOutput"] == {"answer": 42}
        assert "evaluationCriterias" not in snapshot
        # Legacy snapshot id is converted to a GUID
        uuid.UUID(snapshot["id"])

    def test_legacy_defaults_expected_output_when_missing(self):
        item = _eval_item({})
        snapshot = LEGACY.build_eval_snapshot(item)
        assert snapshot["expectedOutput"] == {}

    def test_coded_passes_evaluation_criterias_directly(self):
        criterias = {"Evaluator": {"expectedOutput": {"answer": 42}}}
        item = _eval_item(criterias)
        snapshot = CODED.build_eval_snapshot(item)
        assert snapshot["evaluationCriterias"] == criterias
        assert "expectedOutput" not in snapshot
        assert snapshot["id"] == "my-eval-item"


class TestUpdateEvalRunPayload:
    def test_legacy_payload_uses_assertion_runs_and_evaluator_scores(self):
        payload = LEGACY.build_update_eval_run_payload(
            runs=[{"r": 1}],
            scores=[{"s": 1}],
            eval_run_id="run-1",
            actual_output={"out": 1},
            execution_time=1.5,
            status=2,
        )
        assert payload["assertionRuns"] == [{"r": 1}]
        assert payload["result"]["evaluatorScores"] == [{"s": 1}]
        assert payload["completionMetrics"] == {"duration": 1500}
        assert "evaluatorRuns" not in payload

    def test_coded_payload_uses_evaluator_runs_and_scores(self):
        payload = CODED.build_update_eval_run_payload(
            runs=[{"r": 1}],
            scores=[{"s": 1}],
            eval_run_id="run-1",
            actual_output={"out": 1},
            execution_time=1.5,
            status=2,
        )
        assert payload["evaluatorRuns"] == [{"r": 1}]
        assert payload["result"]["scores"] == [{"s": 1}]
        assert payload["completionMetrics"] == {"duration": 1500}
        assert "assertionRuns" not in payload
