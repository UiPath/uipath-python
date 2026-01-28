"""Tests for CLI telemetry functionality."""

import os
from typing import Any
from unittest.mock import patch

import pytest

from uipath._cli._telemetry import (
    CLI_COMMAND_COMPLETED,
    CLI_COMMAND_FAILED,
    CLI_COMMAND_STARTED,
    CliTelemetryTracker,
    track_cli_command,
)


class TestEventNameConstants:
    """Test telemetry event name constants."""

    def test_cli_command_event_name_templates(self):
        """Test CLI command event name templates."""
        assert CLI_COMMAND_STARTED == "Cli.{command}.Start.URT"
        assert CLI_COMMAND_COMPLETED == "Cli.{command}.End.URT"
        assert CLI_COMMAND_FAILED == "Cli.{command}.Failed.URT"


class TestCliTelemetryTrackerInit:
    """Test CliTelemetryTracker initialization."""

    def test_init_creates_empty_tracking_dict(self):
        """Test that initialization creates empty tracking dictionary."""
        tracker = CliTelemetryTracker()

        assert tracker._start_times == {}


class TestCliTelemetryTrackerGetEventName:
    """Test event name generation."""

    def test_get_event_name_start(self):
        """Test event name for start status."""
        assert (
            CliTelemetryTracker._get_event_name("pack", "Start") == "Cli.Pack.Start.URT"
        )

    def test_get_event_name_end(self):
        """Test event name for end status."""
        assert (
            CliTelemetryTracker._get_event_name("publish", "End")
            == "Cli.Publish.End.URT"
        )

    def test_get_event_name_failed(self):
        """Test event name for failed status."""
        assert (
            CliTelemetryTracker._get_event_name("run", "Failed") == "Cli.Run.Failed.URT"
        )

    def test_get_event_name_lowercase_command(self):
        """Test that command is capitalized."""
        assert (
            CliTelemetryTracker._get_event_name("init", "Start") == "Cli.Init.Start.URT"
        )


class TestCliTelemetryTrackerEnrichProperties:
    """Test property enrichment with context information."""

    def test_enrich_properties_adds_source(self):
        """Test that source and application name are always added."""
        tracker = CliTelemetryTracker()
        properties: dict[str, Any] = {}

        tracker._enrich_properties(properties)

        assert properties["Source"] == "uipath-python-cli"
        assert properties["ApplicationName"] == "UiPath.Cli"

    def test_enrich_properties_adds_env_vars(self):
        """Test that environment variables are added when present."""
        tracker = CliTelemetryTracker()
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
            tracker._enrich_properties(properties)

        assert properties["ProjectId"] == "project-123"
        assert properties["CloudOrganizationId"] == "org-456"
        assert properties["CloudUserId"] == "user-789"
        assert properties["TenantId"] == "tenant-abc"

    def test_enrich_properties_skips_missing_env_vars(self):
        """Test that missing environment variables are not added."""
        tracker = CliTelemetryTracker()
        properties: dict[str, Any] = {}

        with patch.dict(os.environ, {}, clear=True):
            for key in [
                "UIPATH_PROJECT_ID",
                "UIPATH_CLOUD_ORGANIZATION_ID",
                "UIPATH_CLOUD_USER_ID",
                "UIPATH_TENANT_ID",
            ]:
                os.environ.pop(key, None)

            tracker._enrich_properties(properties)

        assert "ProjectId" not in properties
        assert "CloudOrganizationId" not in properties
        assert "CloudUserId" not in properties
        assert "TenantId" not in properties


class TestCliTelemetryTrackerTrackCommandStart:
    """Test command start tracking."""

    @patch("uipath._cli._telemetry.track_event")
    def test_track_command_start_tracks_event(self, mock_track_event):
        """Test that command start event is tracked."""
        tracker = CliTelemetryTracker()

        tracker.track_command_start("pack")

        mock_track_event.assert_called_once()
        call_args = mock_track_event.call_args
        assert call_args[0][0] == "Cli.Pack.Start.URT"
        properties = call_args[0][1]
        assert properties["Command"] == "pack"
        assert properties["Source"] == "uipath-python-cli"

    @patch("uipath._cli._telemetry.track_event")
    def test_track_command_start_stores_start_time(self, mock_track_event):
        """Test that command start time is stored."""
        tracker = CliTelemetryTracker()

        tracker.track_command_start("publish")

        assert "publish" in tracker._start_times

    @patch("uipath._cli._telemetry.track_event")
    def test_track_command_start_handles_exception(self, mock_track_event):
        """Test that exceptions in tracking are caught."""
        mock_track_event.side_effect = Exception("Track failed")
        tracker = CliTelemetryTracker()

        # Should not raise exception
        tracker.track_command_start("pack")


class TestCliTelemetryTrackerTrackCommandEnd:
    """Test command end tracking."""

    @patch("uipath._cli._telemetry.track_event")
    def test_track_command_end_tracks_event(self, mock_track_event):
        """Test that command end event is tracked."""
        tracker = CliTelemetryTracker()
        tracker._start_times["pack"] = 1000.0

        with patch("time.time", return_value=1002.0):
            tracker.track_command_end("pack")

        mock_track_event.assert_called_once()
        call_args = mock_track_event.call_args
        assert call_args[0][0] == "Cli.Pack.End.URT"
        properties = call_args[0][1]
        assert properties["Command"] == "pack"
        assert properties["Success"] is True
        assert properties["DurationMs"] == 2000

    @patch("uipath._cli._telemetry.track_event")
    def test_track_command_end_with_explicit_duration(self, mock_track_event):
        """Test that explicit duration is used when provided."""
        tracker = CliTelemetryTracker()

        tracker.track_command_end("publish", duration_ms=1500)

        properties = mock_track_event.call_args[0][1]
        assert properties["DurationMs"] == 1500

    @patch("uipath._cli._telemetry.track_event")
    def test_track_command_end_handles_exception(self, mock_track_event):
        """Test that exceptions in tracking are caught."""
        mock_track_event.side_effect = Exception("Track failed")
        tracker = CliTelemetryTracker()

        # Should not raise exception
        tracker.track_command_end("pack")


class TestCliTelemetryTrackerTrackCommandFailed:
    """Test command failed tracking."""

    @patch("uipath._cli._telemetry.track_event")
    def test_track_command_failed_tracks_event(self, mock_track_event):
        """Test that command failed event is tracked."""
        tracker = CliTelemetryTracker()
        tracker._start_times["run"] = 1000.0
        exception = ValueError("Test error message")

        with patch("time.time", return_value=1003.0):
            tracker.track_command_failed("run", exception=exception)

        mock_track_event.assert_called_once()
        call_args = mock_track_event.call_args
        assert call_args[0][0] == "Cli.Run.Failed.URT"
        properties = call_args[0][1]
        assert properties["Command"] == "run"
        assert properties["Success"] is False
        assert properties["DurationMs"] == 3000
        assert properties["ErrorType"] == "ValueError"
        assert "Test error message" in properties["ErrorMessage"]

    @patch("uipath._cli._telemetry.track_event")
    def test_track_command_failed_truncates_long_error_messages(self, mock_track_event):
        """Test that error messages are truncated to 500 characters."""
        tracker = CliTelemetryTracker()
        long_message = "x" * 1000
        exception = ValueError(long_message)

        tracker.track_command_failed("run", exception=exception)

        properties = mock_track_event.call_args[0][1]
        assert len(properties["ErrorMessage"]) == 500

    @patch("uipath._cli._telemetry.track_event")
    def test_track_command_failed_handles_exception(self, mock_track_event):
        """Test that exceptions in tracking are caught."""
        mock_track_event.side_effect = Exception("Track failed")
        tracker = CliTelemetryTracker()

        # Should not raise exception
        tracker.track_command_failed("run", exception=ValueError("Error"))


class TestCliTelemetryTrackerFlush:
    """Test flush functionality."""

    @patch("uipath._cli._telemetry.flush_events")
    def test_flush_calls_flush_events(self, mock_flush):
        """Test that flush calls flush_events."""
        tracker = CliTelemetryTracker()

        tracker.flush()

        mock_flush.assert_called_once()

    @patch("uipath._cli._telemetry.flush_events")
    def test_flush_handles_exception(self, mock_flush):
        """Test that exceptions in flush are caught."""
        mock_flush.side_effect = Exception("Flush failed")
        tracker = CliTelemetryTracker()

        # Should not raise exception
        tracker.flush()


class TestTrackCliCommandDecorator:
    """Test the track_cli_command decorator."""

    @patch("uipath._cli._telemetry.flush_events")
    @patch("uipath._cli._telemetry.track_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_decorator_tracks_start_event(
        self, mock_enabled, mock_track_event, mock_flush
    ):
        """Test that decorator tracks start event."""

        @track_cli_command("pack")
        def my_command():
            return "result"

        my_command()

        # Should have at least 2 calls: Start and End
        assert mock_track_event.call_count >= 2

        # First call should be Start
        first_call = mock_track_event.call_args_list[0]
        assert first_call[0][0] == "Cli.Pack.Start.URT"
        assert first_call[0][1]["Command"] == "pack"

    @patch("uipath._cli._telemetry.flush_events")
    @patch("uipath._cli._telemetry.track_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_decorator_tracks_end_event_on_success(
        self, mock_enabled, mock_track_event, mock_flush
    ):
        """Test that decorator tracks end event on successful completion."""

        @track_cli_command("publish")
        def my_command():
            return "result"

        result = my_command()

        assert result == "result"

        # Second call should be End
        second_call = mock_track_event.call_args_list[1]
        assert second_call[0][0] == "Cli.Publish.End.URT"
        properties = second_call[0][1]
        assert properties["Command"] == "publish"
        assert properties["Success"] is True
        assert "DurationMs" in properties

    @patch("uipath._cli._telemetry.flush_events")
    @patch("uipath._cli._telemetry.track_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_decorator_tracks_failed_event_on_exception(
        self, mock_enabled, mock_track_event, mock_flush
    ):
        """Test that decorator tracks failed event when exception is raised."""

        @track_cli_command("run")
        def my_command():
            raise ValueError("Test error message")

        with pytest.raises(ValueError, match="Test error message"):
            my_command()

        # Second call should be Failed
        second_call = mock_track_event.call_args_list[1]
        assert second_call[0][0] == "Cli.Run.Failed.URT"
        properties = second_call[0][1]
        assert properties["Command"] == "run"
        assert properties["Success"] is False
        assert properties["ErrorType"] == "ValueError"
        assert "Test error message" in properties["ErrorMessage"]

    @patch("uipath._cli._telemetry.flush_events")
    @patch("uipath._cli._telemetry.track_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_decorator_flushes_events(self, mock_enabled, mock_track_event, mock_flush):
        """Test that decorator flushes events after command."""

        @track_cli_command("init")
        def my_command():
            return "result"

        my_command()

        mock_flush.assert_called_once()

    @patch("uipath._cli._telemetry.flush_events")
    @patch("uipath._cli._telemetry.track_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_decorator_flushes_events_on_exception(
        self, mock_enabled, mock_track_event, mock_flush
    ):
        """Test that decorator flushes events even when exception is raised."""

        @track_cli_command("new")
        def my_command():
            raise RuntimeError("Boom")

        with pytest.raises(RuntimeError):
            my_command()

        mock_flush.assert_called_once()

    @patch("uipath._cli._telemetry.flush_events")
    @patch("uipath._cli._telemetry.track_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=False)
    def test_decorator_skips_telemetry_when_disabled(
        self, mock_enabled, mock_track_event, mock_flush
    ):
        """Test that decorator skips telemetry when disabled."""

        @track_cli_command("pack")
        def my_command():
            return "result"

        result = my_command()

        assert result == "result"
        mock_track_event.assert_not_called()
        mock_flush.assert_not_called()

    @patch("uipath._cli._telemetry.flush_events")
    @patch("uipath._cli._telemetry.track_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_decorator_preserves_function_arguments(
        self, mock_enabled, mock_track_event, mock_flush
    ):
        """Test that decorator preserves function arguments."""

        @track_cli_command("invoke")
        def my_command(arg1, arg2, kwarg1=None):
            return f"{arg1}-{arg2}-{kwarg1}"

        result = my_command("a", "b", kwarg1="c")

        assert result == "a-b-c"

    @patch("uipath._cli._telemetry.flush_events")
    @patch("uipath._cli._telemetry.track_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_decorator_calculates_duration(
        self, mock_enabled, mock_track_event, mock_flush
    ):
        """Test that decorator calculates duration in milliseconds."""
        import time

        @track_cli_command("pack")
        def my_command():
            time.sleep(0.1)  # Sleep 100ms
            return "result"

        my_command()

        second_call = mock_track_event.call_args_list[1]
        properties = second_call[0][1]
        # Duration should be at least 100ms
        assert properties["DurationMs"] >= 100


class TestExceptionHandling:
    """Test that telemetry never breaks the main CLI."""

    @patch("uipath._cli._telemetry.flush_events")
    @patch("uipath._cli._telemetry.track_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_track_event_exception_does_not_break_command(
        self, mock_enabled, mock_track_event, mock_flush
    ):
        """Test that exceptions in track_event don't break the command."""
        mock_track_event.side_effect = Exception("Telemetry failed")

        @track_cli_command("pack")
        def my_command():
            return "result"

        # Should not raise exception
        result = my_command()
        assert result == "result"

    @patch("uipath._cli._telemetry.flush_events")
    @patch("uipath._cli._telemetry.track_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_flush_events_exception_does_not_break_command(
        self, mock_enabled, mock_track_event, mock_flush
    ):
        """Test that exceptions in flush_events don't break the command."""
        mock_flush.side_effect = Exception("Flush failed")

        @track_cli_command("publish")
        def my_command():
            return "result"

        # Should not raise exception
        result = my_command()
        assert result == "result"

    @patch("uipath._cli._telemetry.flush_events")
    @patch("uipath._cli._telemetry.track_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_track_event_exception_still_allows_command_exception_to_propagate(
        self, mock_enabled, mock_track_event, mock_flush
    ):
        """Test that command exceptions propagate even when telemetry fails."""
        # First call succeeds (Start), second call fails (End)
        mock_track_event.side_effect = [None, Exception("Telemetry failed")]

        @track_cli_command("run")
        def my_command():
            raise ValueError("Command error")

        # Command exception should still propagate
        with pytest.raises(ValueError, match="Command error"):
            my_command()
