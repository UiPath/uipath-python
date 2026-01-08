"""Tests for EvalTelemetrySubscriber functionality."""

import os
from typing import Any
from unittest.mock import patch

import pytest

from uipath._cli._evals._models._evaluation_set import EvaluationItem
from uipath._cli._evals._telemetry import (
    EVAL_RUN_COMPLETED,
    EVAL_RUN_FAILED,
    EVAL_RUN_STARTED,
    EVAL_SET_RUN_COMPLETED,
    EVAL_SET_RUN_FAILED,
    EVAL_SET_RUN_STARTED,
    EvalTelemetrySubscriber,
)
from uipath._events._event_bus import EventBus
from uipath._events._events import (
    EvalItemExceptionDetails,
    EvalRunCreatedEvent,
    EvalRunUpdatedEvent,
    EvalSetRunCreatedEvent,
    EvalSetRunUpdatedEvent,
)
from uipath.eval.models import EvalItemResult, NumericEvaluationResult


class TestEventNameConstants:
    """Test telemetry event name constants."""

    def test_eval_set_run_event_names(self):
        """Test eval set run event name constants."""
        assert EVAL_SET_RUN_STARTED == "EvalSetRun.Start.URT"
        assert EVAL_SET_RUN_COMPLETED == "EvalSetRun.End.URT"
        assert EVAL_SET_RUN_FAILED == "EvalSetRun.Failed.URT"

    def test_eval_run_event_names(self):
        """Test eval run event name constants."""
        assert EVAL_RUN_STARTED == "EvalRun.Start.URT"
        assert EVAL_RUN_COMPLETED == "EvalRun.End.URT"
        assert EVAL_RUN_FAILED == "EvalRun.Failed.URT"


class TestEvalTelemetrySubscriberInit:
    """Test EvalTelemetrySubscriber initialization."""

    def test_init_creates_empty_tracking_dicts(self):
        """Test that initialization creates empty tracking dictionaries."""
        subscriber = EvalTelemetrySubscriber()

        assert subscriber._eval_set_start_times == {}
        assert subscriber._eval_run_start_times == {}
        assert subscriber._eval_set_info == {}
        assert subscriber._eval_run_info == {}


class TestEvalTelemetrySubscriberSubscription:
    """Test subscription to event bus."""

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.is_telemetry_enabled", return_value=True)
    async def test_subscribe_when_telemetry_enabled(self, mock_is_enabled):
        """Test that subscriber registers handlers when telemetry is enabled."""
        subscriber = EvalTelemetrySubscriber()
        event_bus = EventBus()

        await subscriber.subscribe_to_eval_runtime_events(event_bus)

        # Verify handlers are registered (event bus should have subscribers)
        assert len(event_bus._subscribers) == 4

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.is_telemetry_enabled", return_value=False)
    async def test_subscribe_skipped_when_telemetry_disabled(self, mock_is_enabled):
        """Test that subscription is skipped when telemetry is disabled."""
        subscriber = EvalTelemetrySubscriber()
        event_bus = EventBus()

        await subscriber.subscribe_to_eval_runtime_events(event_bus)

        # Verify no handlers are registered
        assert len(event_bus._subscribers) == 0


class TestEvalSetRunCreated:
    """Test eval set run created event handling."""

    def _create_eval_set_run_created_event(
        self,
        execution_id: str = "exec-123",
        eval_set_id: str = "eval-set-1",
        eval_set_run_id: str | None = "run-456",
        entrypoint: str = "agent.py",
        no_of_evals: int = 5,
        evaluators: list[Any] | None = None,
    ) -> EvalSetRunCreatedEvent:
        """Helper to create EvalSetRunCreatedEvent."""
        return EvalSetRunCreatedEvent(
            execution_id=execution_id,
            eval_set_id=eval_set_id,
            eval_set_run_id=eval_set_run_id,
            entrypoint=entrypoint,
            no_of_evals=no_of_evals,
            evaluators=evaluators or [],
        )

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_on_eval_set_run_created_tracks_event(self, mock_track_event):
        """Test that eval set run created event is tracked."""
        subscriber = EvalTelemetrySubscriber()
        event = self._create_eval_set_run_created_event()

        await subscriber._on_eval_set_run_created(event)

        mock_track_event.assert_called_once()
        call_args = mock_track_event.call_args
        assert call_args[0][0] == EVAL_SET_RUN_STARTED
        properties = call_args[0][1]
        assert properties["EvalSetId"] == "eval-set-1"
        assert properties["Entrypoint"] == "agent.py"
        assert properties["EvalCount"] == 5
        assert properties["EvaluatorCount"] == 0
        assert properties["EvalSetRunId"] == "run-456"

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_on_eval_set_run_created_stores_start_time(self, mock_track_event):
        """Test that eval set run start time is stored."""
        subscriber = EvalTelemetrySubscriber()
        event = self._create_eval_set_run_created_event(execution_id="exec-789")

        await subscriber._on_eval_set_run_created(event)

        assert "exec-789" in subscriber._eval_set_start_times
        assert "exec-789" in subscriber._eval_set_info

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_on_eval_set_run_created_without_run_id(self, mock_track_event):
        """Test event tracking when eval_set_run_id is None falls back to execution_id."""
        subscriber = EvalTelemetrySubscriber()
        event = self._create_eval_set_run_created_event(eval_set_run_id=None)

        await subscriber._on_eval_set_run_created(event)

        call_args = mock_track_event.call_args
        properties = call_args[0][1]
        # When eval_set_run_id is None, it falls back to execution_id
        assert properties["EvalSetRunId"] == "exec-123"  # Falls back to execution_id


class TestEvalRunCreated:
    """Test eval run created event handling."""

    def _create_eval_run_created_event(
        self,
        execution_id: str = "exec-123",
        eval_item_id: str = "item-1",
        eval_item_name: str = "Test Eval",
    ) -> EvalRunCreatedEvent:
        """Helper to create EvalRunCreatedEvent."""
        eval_item = EvaluationItem(
            id=eval_item_id,
            name=eval_item_name,
            inputs={},
            expected_agent_behavior="",
            evaluation_criterias={},
        )
        return EvalRunCreatedEvent(
            execution_id=execution_id,
            eval_item=eval_item,
        )

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_on_eval_run_created_tracks_event(self, mock_track_event):
        """Test that eval run created event is tracked."""
        subscriber = EvalTelemetrySubscriber()
        event = self._create_eval_run_created_event()

        await subscriber._on_eval_run_created(event)

        mock_track_event.assert_called_once()
        call_args = mock_track_event.call_args
        assert call_args[0][0] == EVAL_RUN_STARTED
        properties = call_args[0][1]
        assert properties["EvalItemId"] == "item-1"
        assert properties["EvalItemName"] == "Test Eval"

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_on_eval_run_created_stores_start_time(self, mock_track_event):
        """Test that eval run start time is stored."""
        subscriber = EvalTelemetrySubscriber()
        event = self._create_eval_run_created_event(execution_id="exec-456")

        await subscriber._on_eval_run_created(event)

        assert "exec-456" in subscriber._eval_run_start_times
        assert "exec-456" in subscriber._eval_run_info


class TestEvalRunUpdated:
    """Test eval run updated event handling."""

    def _create_eval_run_updated_event(
        self,
        execution_id: str = "exec-123",
        eval_item_id: str = "item-1",
        eval_item_name: str = "Test Eval",
        success: bool = True,
        agent_execution_time: float = 1.5,
        eval_results: list[Any] | None = None,
        exception_details: EvalItemExceptionDetails | None = None,
    ) -> EvalRunUpdatedEvent:
        """Helper to create EvalRunUpdatedEvent."""
        eval_item = EvaluationItem(
            id=eval_item_id,
            name=eval_item_name,
            inputs={},
            expected_agent_behavior="",
            evaluation_criterias={},
        )
        if eval_results is None:
            eval_results = []
        return EvalRunUpdatedEvent(
            execution_id=execution_id,
            eval_item=eval_item,
            eval_results=eval_results,
            success=success,
            agent_output={},
            agent_execution_time=agent_execution_time,
            spans=[],
            logs=[],
            exception_details=exception_details,
        )

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_on_eval_run_updated_success(self, mock_track_event):
        """Test that successful eval run completion is tracked."""
        subscriber = EvalTelemetrySubscriber()
        subscriber._eval_run_start_times["exec-123"] = 1000.0
        subscriber._eval_run_info["exec-123"] = {
            "eval_item_id": "item-1",
            "eval_item_name": "Test Eval",
        }
        event = self._create_eval_run_updated_event(success=True)

        with patch("time.time", return_value=1002.0):
            await subscriber._on_eval_run_updated(event)

        mock_track_event.assert_called_once()
        call_args = mock_track_event.call_args
        assert call_args[0][0] == EVAL_RUN_COMPLETED
        properties = call_args[0][1]
        assert properties["Success"] is True
        assert properties["DurationMs"] == 2000  # 2 seconds

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_on_eval_run_updated_failure(self, mock_track_event):
        """Test that failed eval run is tracked with EVAL_RUN_FAILED."""
        subscriber = EvalTelemetrySubscriber()
        exception_details = EvalItemExceptionDetails(
            exception=ValueError("Test error"),
            runtime_exception=True,
        )
        event = self._create_eval_run_updated_event(
            success=False,
            exception_details=exception_details,
        )

        await subscriber._on_eval_run_updated(event)

        call_args = mock_track_event.call_args
        assert call_args[0][0] == EVAL_RUN_FAILED
        properties = call_args[0][1]
        assert properties["Success"] is False
        assert properties["ErrorType"] == "ValueError"
        assert "Test error" in properties["ErrorMessage"]
        assert properties["IsRuntimeException"] is True

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_on_eval_run_updated_with_scores(self, mock_track_event):
        """Test that average score is calculated and tracked."""
        subscriber = EvalTelemetrySubscriber()
        eval_results = [
            EvalItemResult(
                evaluator_id="eval-1",
                result=NumericEvaluationResult(score=0.8, details="Good"),
            ),
            EvalItemResult(
                evaluator_id="eval-2",
                result=NumericEvaluationResult(score=0.6, details="OK"),
            ),
        ]
        event = self._create_eval_run_updated_event(eval_results=eval_results)

        await subscriber._on_eval_run_updated(event)

        properties = mock_track_event.call_args[0][1]
        assert properties["AverageScore"] == 0.7  # (0.8 + 0.6) / 2
        assert properties["EvaluatorCount"] == 2

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_on_eval_run_updated_agent_execution_time_converted_to_ms(
        self, mock_track_event
    ):
        """Test that agent execution time is converted to milliseconds."""
        subscriber = EvalTelemetrySubscriber()
        event = self._create_eval_run_updated_event(agent_execution_time=2.5)

        await subscriber._on_eval_run_updated(event)

        properties = mock_track_event.call_args[0][1]
        assert properties["AgentExecutionTimeMs"] == 2500  # 2.5 seconds = 2500 ms


class TestEvalSetRunUpdated:
    """Test eval set run updated event handling."""

    def _create_eval_set_run_updated_event(
        self,
        execution_id: str = "exec-123",
        evaluator_scores: dict[str, Any] | None = None,
        success: bool = True,
    ) -> EvalSetRunUpdatedEvent:
        """Helper to create EvalSetRunUpdatedEvent."""
        return EvalSetRunUpdatedEvent(
            execution_id=execution_id,
            evaluator_scores=evaluator_scores or {},
            success=success,
        )

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_on_eval_set_run_updated_success(self, mock_track_event):
        """Test that successful eval set completion is tracked."""
        subscriber = EvalTelemetrySubscriber()
        subscriber._eval_set_start_times["exec-123"] = 1000.0
        subscriber._eval_set_info["exec-123"] = {
            "eval_set_id": "set-1",
            "eval_set_run_id": "run-1",
            "entrypoint": "agent.py",
            "no_of_evals": 3,
        }
        event = self._create_eval_set_run_updated_event(
            evaluator_scores={"eval-1": 0.9, "eval-2": 0.7},
            success=True,
        )

        with patch("time.time", return_value=1005.0):
            await subscriber._on_eval_set_run_updated(event)

        mock_track_event.assert_called_once()
        call_args = mock_track_event.call_args
        assert call_args[0][0] == EVAL_SET_RUN_COMPLETED
        properties = call_args[0][1]
        assert properties["Success"] is True
        assert properties["DurationMs"] == 5000
        assert properties["AverageScore"] == 0.8  # (0.9 + 0.7) / 2
        assert properties["EvalSetId"] == "set-1"
        assert properties["EvalSetRunId"] == "run-1"
        assert properties["Entrypoint"] == "agent.py"
        assert properties["EvalCount"] == 3

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_on_eval_set_run_updated_failure(self, mock_track_event):
        """Test that failed eval set is tracked with EVAL_SET_RUN_FAILED."""
        subscriber = EvalTelemetrySubscriber()
        event = self._create_eval_set_run_updated_event(success=False)

        await subscriber._on_eval_set_run_updated(event)

        call_args = mock_track_event.call_args
        assert call_args[0][0] == EVAL_SET_RUN_FAILED
        properties = call_args[0][1]
        assert properties["Success"] is False

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_on_eval_set_run_updated_includes_evaluator_scores(
        self, mock_track_event
    ):
        """Test that individual evaluator scores are included."""
        subscriber = EvalTelemetrySubscriber()
        event = self._create_eval_set_run_updated_event(
            evaluator_scores={"accuracy": 0.95, "relevance-check": 0.85},
        )

        await subscriber._on_eval_set_run_updated(event)

        properties = mock_track_event.call_args[0][1]
        assert properties["Score_accuracy"] == 0.95
        assert (
            properties["Score_relevance_check"] == 0.85
        )  # dash replaced with underscore


class TestEnrichProperties:
    """Test property enrichment with context information."""

    def test_enrich_properties_adds_source(self):
        """Test that source and application name are always added."""
        subscriber = EvalTelemetrySubscriber()
        properties: dict[str, Any] = {}

        subscriber._enrich_properties(properties)

        assert properties["Source"] == "uipath-python-cli"
        assert properties["ApplicationName"] == "UiPath.Eval"

    def test_enrich_properties_adds_env_vars(self):
        """Test that environment variables are added when present."""
        subscriber = EvalTelemetrySubscriber()
        properties: dict[str, Any] = {}

        with patch.dict(
            os.environ,
            {
                "UIPATH_PROJECT_ID": "project-123",
                "UIPATH_CLOUD_ORGANIZATION_ID": "org-456",
                "UIPATH_CLOUD_USER_ID": "user-789",
                "UIPATH_TENANT_ID": "tenant-abc",
            },
        ):
            subscriber._enrich_properties(properties)

        assert properties["ProjectId"] == "project-123"
        assert properties["CloudOrganizationId"] == "org-456"
        assert properties["CloudUserId"] == "user-789"
        assert properties["TenantId"] == "tenant-abc"

    def test_enrich_properties_skips_missing_env_vars(self):
        """Test that missing environment variables are not added."""
        subscriber = EvalTelemetrySubscriber()
        properties: dict[str, Any] = {}

        with patch.dict(os.environ, {}, clear=True):
            # Remove env vars if they exist
            for key in [
                "UIPATH_PROJECT_ID",
                "UIPATH_CLOUD_ORGANIZATION_ID",
                "UIPATH_CLOUD_USER_ID",
                "UIPATH_TENANT_ID",
            ]:
                os.environ.pop(key, None)

            subscriber._enrich_properties(properties)

        assert "ProjectId" not in properties
        assert "CloudOrganizationId" not in properties
        assert "CloudUserId" not in properties
        assert "TenantId" not in properties


class TestExceptionHandling:
    """Test that telemetry never breaks the main application."""

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_eval_set_run_created_handles_exception(self, mock_track_event):
        """Test that exceptions in event handling are caught."""
        mock_track_event.side_effect = Exception("Track failed")
        subscriber = EvalTelemetrySubscriber()
        event = EvalSetRunCreatedEvent(
            execution_id="exec-1",
            eval_set_id="set-1",
            entrypoint="agent.py",
            no_of_evals=1,
            evaluators=[],
        )

        # Should not raise exception
        await subscriber._on_eval_set_run_created(event)

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_eval_run_created_handles_exception(self, mock_track_event):
        """Test that exceptions in eval run created handling are caught."""
        mock_track_event.side_effect = Exception("Track failed")
        subscriber = EvalTelemetrySubscriber()
        eval_item = EvaluationItem(
            id="item-1",
            name="Test",
            inputs={},
            expected_agent_behavior="",
            evaluation_criterias={},
        )
        event = EvalRunCreatedEvent(execution_id="exec-1", eval_item=eval_item)

        # Should not raise exception
        await subscriber._on_eval_run_created(event)

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_eval_run_updated_handles_exception(self, mock_track_event):
        """Test that exceptions in eval run updated handling are caught."""
        mock_track_event.side_effect = Exception("Track failed")
        subscriber = EvalTelemetrySubscriber()
        eval_item = EvaluationItem(
            id="item-1",
            name="Test",
            inputs={},
            expected_agent_behavior="",
            evaluation_criterias={},
        )
        event = EvalRunUpdatedEvent(
            execution_id="exec-1",
            eval_item=eval_item,
            eval_results=[],
            success=True,
            agent_output={},
            agent_execution_time=1.0,
            spans=[],
            logs=[],
        )

        # Should not raise exception
        await subscriber._on_eval_run_updated(event)

    @pytest.mark.asyncio
    @patch("uipath._cli._evals._telemetry.track_event")
    async def test_eval_set_run_updated_handles_exception(self, mock_track_event):
        """Test that exceptions in eval set run updated handling are caught."""
        mock_track_event.side_effect = Exception("Track failed")
        subscriber = EvalTelemetrySubscriber()
        event = EvalSetRunUpdatedEvent(
            execution_id="exec-1",
            evaluator_scores={},
            success=True,
        )

        # Should not raise exception
        await subscriber._on_eval_set_run_updated(event)
