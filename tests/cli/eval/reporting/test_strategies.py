"""Tests for evaluation reporting strategies.

This module tests the strategy classes including:
- LegacyEvalReportingStrategy
- CodedEvalReportingStrategy
- ID conversion behavior
- Payload structure generation
"""

import uuid

import pytest

from uipath._cli._evals._reporting._strategies import (
    CodedEvalReportingStrategy,
    LegacyEvalReportingStrategy,
)


class TestLegacyEvalReportingStrategy:
    """Tests for LegacyEvalReportingStrategy."""

    @pytest.fixture
    def strategy(self):
        """Create a LegacyEvalReportingStrategy instance."""
        return LegacyEvalReportingStrategy()

    def test_endpoint_suffix_is_empty(self, strategy):
        """Test that legacy strategy has empty endpoint suffix."""
        assert strategy.endpoint_suffix == ""

    def test_convert_id_with_valid_uuid(self, strategy):
        """Test that valid UUIDs are returned unchanged."""
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        assert strategy.convert_id(valid_uuid) == valid_uuid

    def test_convert_id_with_string_id(self, strategy):
        """Test that string IDs are converted to deterministic UUIDs."""
        string_id = "my-custom-id"
        result = strategy.convert_id(string_id)

        # Result should be a valid UUID
        uuid.UUID(result)

        # Same input should produce same output (deterministic)
        assert strategy.convert_id(string_id) == result

    def test_convert_id_with_different_strings_produces_different_uuids(self, strategy):
        """Test that different string IDs produce different UUIDs."""
        id1 = strategy.convert_id("id-one")
        id2 = strategy.convert_id("id-two")

        assert id1 != id2

    def test_create_eval_set_run_payload_structure(self, strategy):
        """Test the structure of legacy eval set run payload."""
        from uipath._cli._evals._models._sw_reporting import StudioWebAgentSnapshot

        agent_snapshot = StudioWebAgentSnapshot(
            input_schema={"type": "object"}, output_schema={"type": "object"}
        )

        payload = strategy.create_eval_set_run_payload(
            eval_set_id="test-eval-set",
            agent_snapshot=agent_snapshot,
            no_of_evals=5,
            project_id="test-project",
        )

        assert payload["agentId"] == "test-project"
        assert payload["status"] == 1  # IN_PROGRESS
        assert payload["numberOfEvalsExecuted"] == 5
        assert payload["source"] == 0
        assert "agentSnapshot" in payload

    def test_create_update_eval_run_payload_uses_assertion_runs(self, strategy):
        """Test that legacy update payload uses assertionRuns field."""
        evaluator_runs = [{"evaluatorId": "test-1", "status": 2}]
        evaluator_scores = [{"evaluatorId": "test-1", "value": 0.9}]

        payload = strategy.create_update_eval_run_payload(
            eval_run_id="run-id",
            evaluator_runs=evaluator_runs,
            evaluator_scores=evaluator_scores,
            actual_output={"result": "success"},
            execution_time=5.0,
            success=True,
        )

        assert "assertionRuns" in payload
        assert payload["assertionRuns"] == evaluator_runs
        assert "evaluatorRuns" not in payload
        assert payload["result"]["evaluatorScores"] == evaluator_scores

    def test_create_update_eval_set_run_payload_converts_ids(self, strategy):
        """Test that eval set run update converts evaluator IDs."""
        evaluator_scores = {"my-evaluator": 0.85}

        payload = strategy.create_update_eval_set_run_payload(
            eval_set_run_id="run-id",
            evaluator_scores=evaluator_scores,
            success=True,
        )

        # Check that the evaluator ID was converted
        assert len(payload["evaluatorScores"]) == 1
        score_entry = payload["evaluatorScores"][0]
        assert score_entry["evaluatorId"] != "my-evaluator"  # Should be converted
        # Verify it's a valid UUID
        uuid.UUID(score_entry["evaluatorId"])


class TestCodedEvalReportingStrategy:
    """Tests for CodedEvalReportingStrategy."""

    @pytest.fixture
    def strategy(self):
        """Create a CodedEvalReportingStrategy instance."""
        return CodedEvalReportingStrategy()

    def test_endpoint_suffix_is_coded(self, strategy):
        """Test that coded strategy has 'coded/' endpoint suffix."""
        assert strategy.endpoint_suffix == "coded/"

    def test_convert_id_returns_unchanged(self, strategy):
        """Test that IDs are returned unchanged."""
        string_id = "my-custom-id"
        assert strategy.convert_id(string_id) == string_id

        uuid_id = "550e8400-e29b-41d4-a716-446655440000"
        assert strategy.convert_id(uuid_id) == uuid_id

    def test_create_eval_set_run_payload_keeps_original_id(self, strategy):
        """Test that eval set ID is kept unchanged."""
        from uipath._cli._evals._models._sw_reporting import StudioWebAgentSnapshot

        agent_snapshot = StudioWebAgentSnapshot(
            input_schema={"type": "object"}, output_schema={"type": "object"}
        )

        payload = strategy.create_eval_set_run_payload(
            eval_set_id="my-eval-set-id",
            agent_snapshot=agent_snapshot,
            no_of_evals=3,
            project_id="test-project",
        )

        assert payload["evalSetId"] == "my-eval-set-id"  # Unchanged

    def test_create_update_eval_run_payload_uses_evaluator_runs(self, strategy):
        """Test that coded update payload uses evaluatorRuns field."""
        evaluator_runs = [{"evaluatorId": "test-1", "status": 2}]
        evaluator_scores = [{"evaluatorId": "test-1", "value": 0.9}]

        payload = strategy.create_update_eval_run_payload(
            eval_run_id="run-id",
            evaluator_runs=evaluator_runs,
            evaluator_scores=evaluator_scores,
            actual_output={"result": "success"},
            execution_time=5.0,
            success=True,
        )

        assert "evaluatorRuns" in payload
        assert payload["evaluatorRuns"] == evaluator_runs
        assert "assertionRuns" not in payload
        assert (
            payload["result"]["scores"] == evaluator_scores
        )  # "scores" not "evaluatorScores"

    def test_create_update_eval_set_run_payload_keeps_ids(self, strategy):
        """Test that eval set run update keeps evaluator IDs unchanged."""
        evaluator_scores = {"my-evaluator": 0.85}

        payload = strategy.create_update_eval_set_run_payload(
            eval_set_run_id="run-id",
            evaluator_scores=evaluator_scores,
            success=True,
        )

        # Check that the evaluator ID was NOT converted
        assert len(payload["evaluatorScores"]) == 1
        score_entry = payload["evaluatorScores"][0]
        assert score_entry["evaluatorId"] == "my-evaluator"  # Should be unchanged


class TestStrategyStatusHandling:
    """Tests for status handling in both strategies."""

    @pytest.fixture
    def legacy_strategy(self):
        return LegacyEvalReportingStrategy()

    @pytest.fixture
    def coded_strategy(self):
        return CodedEvalReportingStrategy()

    def test_legacy_success_status(self, legacy_strategy):
        """Test legacy strategy sets COMPLETED status on success."""
        payload = legacy_strategy.create_update_eval_run_payload(
            eval_run_id="run-id",
            evaluator_runs=[],
            evaluator_scores=[],
            actual_output={},
            execution_time=0.0,
            success=True,
        )
        assert payload["status"] == 2  # COMPLETED

    def test_legacy_failure_status(self, legacy_strategy):
        """Test legacy strategy sets FAILED status on failure."""
        payload = legacy_strategy.create_update_eval_run_payload(
            eval_run_id="run-id",
            evaluator_runs=[],
            evaluator_scores=[],
            actual_output={},
            execution_time=0.0,
            success=False,
        )
        assert payload["status"] == 3  # FAILED

    def test_coded_success_status(self, coded_strategy):
        """Test coded strategy sets COMPLETED status on success."""
        payload = coded_strategy.create_update_eval_run_payload(
            eval_run_id="run-id",
            evaluator_runs=[],
            evaluator_scores=[],
            actual_output={},
            execution_time=0.0,
            success=True,
        )
        assert payload["status"] == 2  # COMPLETED

    def test_coded_failure_status(self, coded_strategy):
        """Test coded strategy sets FAILED status on failure."""
        payload = coded_strategy.create_update_eval_run_payload(
            eval_run_id="run-id",
            evaluator_runs=[],
            evaluator_scores=[],
            actual_output={},
            execution_time=0.0,
            success=False,
        )
        assert payload["status"] == 3  # FAILED
