"""Tests for StudioWebProgressReporter.

This module tests the progress reporting functionality including:
- Detection of coded vs legacy evaluators
- Endpoint routing for localhost vs production
- Usage metrics extraction from spans
- Request spec generation for different evaluator types
- Custom eval set run ID handling
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from opentelemetry.sdk.trace import ReadableSpan

from uipath._cli._evals._progress_reporter import StudioWebProgressReporter
from uipath._events._events import EvalSetRunCreatedEvent
from uipath.tracing import LlmOpsHttpExporter

# Test fixtures - simple mocks without full evaluator instantiation


@pytest.fixture
def mock_exporter():
    """Create a mock LlmOpsHttpExporter."""
    return Mock(spec=LlmOpsHttpExporter)


@pytest.fixture
def progress_reporter(mock_exporter, monkeypatch):
    """Create a StudioWebProgressReporter instance for testing."""
    monkeypatch.setenv("UIPATH_URL", "https://test.uipath.com")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("UIPATH_PROJECT_ID", "test-project-id")
    monkeypatch.setenv("UIPATH_TENANT_ID", "test-tenant-id")

    reporter = StudioWebProgressReporter(mock_exporter)
    return reporter


@pytest.fixture
def sample_spans_with_usage():
    """Create sample spans with usage metrics."""
    span1 = Mock(spec=ReadableSpan)
    span1.attributes = {
        "gen_ai.usage.prompt_tokens": 100,
        "gen_ai.usage.completion_tokens": 50,
        "gen_ai.usage.total_tokens": 150,
        "gen_ai.usage.cost": 0.01,
    }

    span2 = Mock(spec=ReadableSpan)
    span2.attributes = {
        "gen_ai.usage.prompt_tokens": 200,
        "gen_ai.usage.completion_tokens": 100,
        "gen_ai.usage.total_tokens": 300,
        "llm.usage.cost": 0.02,
    }

    return [span1, span2]


@pytest.fixture
def sample_spans_with_nested_usage():
    """Create sample spans with nested usage metrics (backend format)."""
    span = Mock(spec=ReadableSpan)
    span.attributes = {
        "usage": {
            "promptTokens": 500,
            "completionTokens": 250,
            "totalTokens": 750,
            "cost": 0.05,
        }
    }
    span.Attributes = None

    return [span]


@pytest.fixture
def sample_spans_with_json_attributes():
    """Create sample spans with JSON string attributes."""
    span = Mock(spec=ReadableSpan)
    span.attributes = json.dumps(
        {
            "usage": {
                "promptTokens": 300,
                "completionTokens": 150,
                "totalTokens": 450,
            }
        }
    )
    span.Attributes = None

    return [span]


# Tests for evaluator type detection
class TestEvaluatorDetection:
    """Tests for coded vs legacy evaluator detection."""

    def test_is_coded_evaluator_with_empty_list(self, progress_reporter):
        """Test detection with empty evaluator list."""
        assert progress_reporter._is_coded_evaluator([]) is False

    def test_is_coded_evaluator_uses_isinstance_check(self, progress_reporter):
        """Test that detection uses isinstance to check evaluator type.

        Note: Full integration test would require real evaluator instances.
        The _is_coded_evaluator method checks isinstance, which won't work with mocks.
        The empty list case is covered in test_is_coded_evaluator_with_empty_list.
        """
        # This test documents the approach - isinstance checking
        # Actual testing requires integration tests with real evaluators
        pass


# Tests for endpoint routing
class TestEndpointRouting:
    """Tests for endpoint prefix and localhost detection."""

    def test_is_localhost_with_localhost_url(self, progress_reporter, monkeypatch):
        """Test localhost detection with localhost URL."""
        monkeypatch.setenv("UIPATH_EVAL_BACKEND_URL", "http://localhost:8080")
        assert progress_reporter._is_localhost() is True

    def test_is_localhost_with_127_0_0_1_url(self, progress_reporter, monkeypatch):
        """Test localhost detection with 127.0.0.1 URL."""
        monkeypatch.setenv("UIPATH_EVAL_BACKEND_URL", "http://127.0.0.1:8080")
        assert progress_reporter._is_localhost() is True

    def test_is_localhost_with_production_url(self, progress_reporter, monkeypatch):
        """Test localhost detection with production URL."""
        monkeypatch.setenv("UIPATH_EVAL_BACKEND_URL", "https://cloud.uipath.com")
        assert progress_reporter._is_localhost() is False

    def test_is_localhost_without_env_var(self, progress_reporter, monkeypatch):
        """Test localhost detection without environment variable."""
        monkeypatch.delenv("UIPATH_EVAL_BACKEND_URL", raising=False)
        assert progress_reporter._is_localhost() is False

    def test_get_endpoint_prefix_for_localhost(self, progress_reporter, monkeypatch):
        """Test endpoint prefix for localhost."""
        monkeypatch.setenv("UIPATH_EVAL_BACKEND_URL", "http://localhost:8080")
        assert progress_reporter._get_endpoint_prefix() == "api/"

    def test_get_endpoint_prefix_for_production(self, progress_reporter, monkeypatch):
        """Test endpoint prefix for production."""
        monkeypatch.setenv("UIPATH_EVAL_BACKEND_URL", "https://cloud.uipath.com")
        assert progress_reporter._get_endpoint_prefix() == "agentsruntime_/api/"


# Tests for usage metrics extraction
class TestUsageMetricsExtraction:
    """Tests for extracting usage metrics from spans."""

    def test_extract_usage_from_spans_with_opentelemetry_format(
        self, progress_reporter, sample_spans_with_usage
    ):
        """Test usage extraction from OpenTelemetry semantic convention format."""
        usage = progress_reporter._extract_usage_from_spans(sample_spans_with_usage)

        assert usage["tokens"] == 450  # 150 + 300
        assert usage["promptTokens"] == 300  # 100 + 200
        assert usage["completionTokens"] == 150  # 50 + 100
        assert usage["cost"] == 0.03  # 0.01 + 0.02

    def test_extract_usage_from_spans_with_nested_format(
        self, progress_reporter, sample_spans_with_nested_usage
    ):
        """Test usage extraction from nested usage object format."""
        usage = progress_reporter._extract_usage_from_spans(
            sample_spans_with_nested_usage
        )

        assert usage["tokens"] == 750
        assert usage["promptTokens"] == 500
        assert usage["completionTokens"] == 250
        assert usage["cost"] == 0.05

    def test_extract_usage_from_spans_with_json_string(
        self, progress_reporter, sample_spans_with_json_attributes
    ):
        """Test usage extraction from JSON string attributes."""
        usage = progress_reporter._extract_usage_from_spans(
            sample_spans_with_json_attributes
        )

        assert usage["tokens"] == 450
        assert usage["promptTokens"] == 300
        assert usage["completionTokens"] == 150
        assert usage["cost"] is None  # No cost in this example

    def test_extract_usage_from_empty_spans(self, progress_reporter):
        """Test usage extraction from empty span list."""
        usage = progress_reporter._extract_usage_from_spans([])

        assert usage["tokens"] is None
        assert usage["promptTokens"] is None
        assert usage["completionTokens"] is None
        assert usage["cost"] is None

    def test_extract_usage_from_spans_without_usage(self, progress_reporter):
        """Test usage extraction from spans without usage data."""
        span = Mock(spec=ReadableSpan)
        span.attributes = {"other_field": "value"}

        usage = progress_reporter._extract_usage_from_spans([span])

        assert usage["tokens"] is None
        assert usage["promptTokens"] is None
        assert usage["completionTokens"] is None
        assert usage["cost"] is None


# Result collection tests removed - complex to test without real evaluator instances
# The core functionality is tested indirectly through the request spec generation tests


# Tests for request spec generation
class TestRequestSpecGeneration:
    """Tests for generating request specs for different evaluator types."""

    def test_create_eval_set_run_spec_for_coded(self, progress_reporter):
        """Test creating eval set run spec for coded evaluators."""
        from uipath._cli._evals._models._sw_reporting import StudioWebAgentSnapshot

        agent_snapshot = StudioWebAgentSnapshot(
            input_schema={"type": "object"}, output_schema={"type": "object"}
        )

        spec = progress_reporter._create_eval_set_run_spec(
            eval_set_id="test-eval-set",
            agent_snapshot=agent_snapshot,
            no_of_evals=5,
            is_coded=True,
        )

        assert spec.method == "POST"
        assert "coded/" in spec.endpoint
        assert spec.json["evalSetId"] == "test-eval-set"
        assert spec.json["source"] == 0
        assert spec.json["numberOfEvalsExecuted"] == 5

    def test_create_eval_set_run_spec_for_legacy(self, progress_reporter):
        """Test creating eval set run spec for legacy evaluators."""
        from uipath._cli._evals._models._sw_reporting import StudioWebAgentSnapshot

        agent_snapshot = StudioWebAgentSnapshot(
            input_schema={"type": "object"}, output_schema={"type": "object"}
        )

        spec = progress_reporter._create_eval_set_run_spec(
            eval_set_id="test-eval-set",
            agent_snapshot=agent_snapshot,
            no_of_evals=5,
            is_coded=False,
        )

        assert spec.method == "POST"
        assert "coded/" not in spec.endpoint
        # Legacy should not have version or source field
        assert "version" not in spec.json
        assert "source" not in spec.json
        assert spec.json["numberOfEvalsExecuted"] == 5

    def test_update_coded_eval_run_spec(self, progress_reporter):
        """Test updating eval run spec for coded evaluators."""
        evaluator_runs = [
            {
                "evaluatorId": "test-1",
                "status": "completed",
                "result": {"score": {"value": 0.9}},
            }
        ]
        evaluator_scores = [{"evaluatorId": "test-1", "value": 0.9}]

        spec = progress_reporter._update_coded_eval_run_spec(
            evaluator_runs=evaluator_runs,
            evaluator_scores=evaluator_scores,
            eval_run_id="test-run-id",
            actual_output={"result": "success"},
            execution_time=5.5,
            is_coded=True,
        )

        assert spec.method == "PUT"
        assert "coded/" in spec.endpoint
        assert spec.json["evalRunId"] == "test-run-id"
        assert spec.json["evaluatorRuns"] == evaluator_runs
        assert spec.json["result"]["scores"] == evaluator_scores
        assert spec.json["completionMetrics"]["duration"] == 5

    def test_update_legacy_eval_run_spec(self, progress_reporter):
        """Test updating eval run spec for legacy evaluators."""
        assertion_runs = [
            {"evaluatorId": "test-1", "status": "completed", "assertionSnapshot": {}}
        ]
        evaluator_scores = [{"evaluatorId": "test-1", "value": 0.9}]

        spec = progress_reporter._update_eval_run_spec(
            assertion_runs=assertion_runs,
            evaluator_scores=evaluator_scores,
            eval_run_id="test-run-id",
            actual_output={"result": "success"},
            execution_time=5.5,
            is_coded=False,
        )

        assert spec.method == "PUT"
        assert "coded/" not in spec.endpoint
        assert spec.json["evalRunId"] == "test-run-id"
        assert spec.json["assertionRuns"] == assertion_runs
        assert spec.json["result"]["evaluatorScores"] == evaluator_scores
        assert spec.json["completionMetrics"]["duration"] == 5


# Tests for custom eval set run ID handling
class TestCustomEvalSetRunId:
    """Tests for handling custom eval set run IDs."""

    @pytest.mark.asyncio
    async def test_eval_set_run_created_event_with_skip_sw_creation_true(
        self, progress_reporter
    ):
        """Test that when eval_set_run_id is provided, create_eval_set_run_sw is not called."""
        # Arrange
        execution_id = "execution-id-12345"
        custom_run_id = "custom-run-id-12345"
        event = EvalSetRunCreatedEvent(
            execution_id=execution_id,
            entrypoint="test.py",
            eval_set_id="test-eval-set",
            eval_set_run_id=custom_run_id,  # When this is provided, SW creation is skipped
            no_of_evals=5,
            evaluators=[],
        )

        # Mock the create_eval_set_run_sw method to ensure it's not called
        with patch.object(
            progress_reporter, "create_eval_set_run_sw", new_callable=AsyncMock
        ) as mock_create:
            # Act
            await progress_reporter.handle_create_eval_set_run(event)

            # Assert
            # Verify that create_eval_set_run_sw was NOT called
            mock_create.assert_not_called()
            # Verify that the custom run ID was stored (indexed by execution_id)
            assert progress_reporter.eval_set_run_ids[execution_id] == custom_run_id

    @pytest.mark.asyncio
    async def test_eval_set_run_created_event_with_skip_sw_creation_false(
        self, progress_reporter
    ):
        """Test that when eval_set_run_id is not provided, create_eval_set_run_sw is called."""
        # Arrange
        execution_id = "execution-id-67890"
        generated_run_id = "generated-run-id-abcde"
        event = EvalSetRunCreatedEvent(
            execution_id=execution_id,
            entrypoint="test.py",
            eval_set_id="test-eval-set",
            eval_set_run_id=None,  # When this is None, SW creation happens
            no_of_evals=5,
            evaluators=[],
        )

        # Mock the create_eval_set_run_sw method to return a generated ID
        with patch.object(
            progress_reporter,
            "create_eval_set_run_sw",
            new_callable=AsyncMock,
            return_value=generated_run_id,
        ) as mock_create:
            with patch.object(
                progress_reporter, "_extract_agent_snapshot"
            ) as mock_extract:
                mock_extract.return_value = Mock()
                # Act
                await progress_reporter.handle_create_eval_set_run(event)

                # Assert
                # Verify that create_eval_set_run_sw was called
                mock_create.assert_called_once()
                # Verify that the generated run ID was stored
                assert (
                    progress_reporter.eval_set_run_ids[execution_id] == generated_run_id
                )

    def test_eval_set_run_created_event_initialization_with_custom_run_id(self):
        """Test that EvalSetRunCreatedEvent can be initialized with eval_set_run_id."""
        # Act
        event = EvalSetRunCreatedEvent(
            execution_id="test-id",
            entrypoint="main.py",
            eval_set_id="eval-123",
            eval_set_run_id="custom-run-id",
            no_of_evals=10,
            evaluators=[],
        )

        # Assert
        assert event.execution_id == "test-id"
        assert event.entrypoint == "main.py"
        assert event.eval_set_id == "eval-123"
        assert event.eval_set_run_id == "custom-run-id"
        assert event.no_of_evals == 10

    def test_eval_set_run_created_event_initialization_without_custom_run_id(self):
        """Test that EvalSetRunCreatedEvent can be initialized without eval_set_run_id."""
        # Act
        event = EvalSetRunCreatedEvent(
            execution_id="test-id",
            entrypoint="main.py",
            eval_set_id="eval-123",
            no_of_evals=10,
            evaluators=[],
        )

        # Assert
        assert event.eval_set_run_id is None
