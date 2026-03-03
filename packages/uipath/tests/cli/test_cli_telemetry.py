"""Tests for CLI telemetry functionality."""

import os
from typing import Any
from unittest.mock import patch

import pytest

from uipath._cli._telemetry import (
    CliTelemetryTracker,
    track_command,
)


class TestGetEventName:
    """Test event name generation."""

    @pytest.mark.parametrize(
        "command, expected",
        [
            ("pack", "Cli.Pack"),
            ("publish", "Cli.Publish"),
            ("run", "Cli.Run"),
            ("initialize", "Cli.Initialize"),
        ],
    )
    def test_get_event_name(self, command, expected):
        assert CliTelemetryTracker._get_event_name(command) == expected


class TestEnrichProperties:
    """Test property enrichment with context information."""

    @patch("uipath._cli._telemetry.version", return_value="1.0.0")
    @patch("uipath._cli._telemetry.get_claim_from_token", return_value=None)
    @patch("uipath._cli._telemetry._get_project_key", return_value=None)
    def test_always_present_fields(self, mock_project_key, mock_claim, mock_version):
        tracker = CliTelemetryTracker()
        properties: dict[str, Any] = {}

        with patch.dict(os.environ, {}, clear=True):
            tracker._enrich_properties(properties)

        assert properties["Source"] == "uipath-python-cli"
        assert properties["ApplicationName"] == "UiPath.AgentCli"
        assert properties["SessionId"] == "nosession"
        assert properties["SDKVersion"] == "1.0.0"
        assert properties["IsGithubCI"] is False

    @patch("uipath._cli._telemetry.version", return_value="1.2.3")
    @patch("uipath._cli._telemetry.get_claim_from_token", return_value="user-789")
    @patch("uipath._cli._telemetry._get_project_key", return_value="project-key-123")
    def test_adds_context_when_available(
        self, mock_project_key, mock_claim, mock_version
    ):
        tracker = CliTelemetryTracker()
        properties: dict[str, Any] = {}

        with patch.dict(
            os.environ,
            {
                "UIPATH_TENANT_ID": "tenant-abc",
                "UIPATH_ORGANIZATION_ID": "org-456",
            },
        ):
            tracker._enrich_properties(properties)

        assert properties["AgentId"] == "project-key-123"
        assert properties["CloudOrganizationId"] == "org-456"
        assert properties["CloudTenantId"] == "tenant-abc"
        assert properties["CloudUserId"] == "user-789"

    @patch("uipath._cli._telemetry.version", side_effect=Exception("not found"))
    @patch("uipath._cli._telemetry.get_claim_from_token", return_value=None)
    @patch("uipath._cli._telemetry._get_project_key", return_value=None)
    def test_skips_missing_context(self, mock_project_key, mock_claim, mock_version):
        tracker = CliTelemetryTracker()
        properties: dict[str, Any] = {}

        with patch.dict(os.environ, {}, clear=True):
            tracker._enrich_properties(properties)

        assert "AgentId" not in properties
        assert "CloudOrganizationId" not in properties
        assert "CloudTenantId" not in properties
        assert "CloudUserId" not in properties
        assert "SDKVersion" not in properties
        assert properties["SessionId"] == "nosession"
        assert properties["IsGithubCI"] is False


class TestTrackCommandDecorator:
    """Test the track_command decorator end-to-end."""

    @patch.object(CliTelemetryTracker, "_enrich_properties")
    @patch("uipath._cli._telemetry.track_cli_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_tracks_success(self, mock_enabled, mock_track_event, mock_enrich):
        @track_command("publish")
        def my_command():
            return "result"

        assert my_command() == "result"

        mock_track_event.assert_called_once()
        properties = mock_track_event.call_args[0][1]
        assert mock_track_event.call_args[0][0] == "Cli.Publish"
        assert properties["Command"] == "publish"
        assert properties["Status"] == "Completed"
        assert properties["Success"] is True
        assert "DurationMs" in properties

    @patch.object(CliTelemetryTracker, "_enrich_properties")
    @patch("uipath._cli._telemetry.track_cli_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_tracks_failure(self, mock_enabled, mock_track_event, mock_enrich):
        @track_command("run")
        def my_command():
            raise ValueError("Test error message")

        with pytest.raises(ValueError, match="Test error message"):
            my_command()

        mock_track_event.assert_called_once()
        properties = mock_track_event.call_args[0][1]
        assert properties["Command"] == "run"
        assert properties["Status"] == "Failed"
        assert properties["Success"] is False
        assert properties["ErrorType"] == "ValueError"
        assert "Test error message" in properties["ErrorMessage"]

    @patch.object(CliTelemetryTracker, "_enrich_properties")
    @patch("uipath._cli._telemetry.track_cli_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_truncates_long_error_messages(
        self, mock_enabled, mock_track_event, mock_enrich
    ):
        @track_command("run")
        def my_command():
            raise ValueError("x" * 1000)

        with pytest.raises(ValueError):
            my_command()

        properties = mock_track_event.call_args[0][1]
        assert len(properties["ErrorMessage"]) == 500

    @patch("uipath._cli._telemetry.track_cli_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=False)
    def test_skips_when_disabled(self, mock_enabled, mock_track_event):
        @track_command("pack")
        def my_command():
            return "result"

        assert my_command() == "result"
        mock_track_event.assert_not_called()

    @patch.object(CliTelemetryTracker, "_enrich_properties")
    @patch("uipath._cli._telemetry.track_cli_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_telemetry_error_does_not_break_command(
        self, mock_enabled, mock_track_event, mock_enrich
    ):
        mock_track_event.side_effect = Exception("Telemetry failed")

        @track_command("pack")
        def my_command():
            return "result"

        assert my_command() == "result"

    @patch.object(CliTelemetryTracker, "_enrich_properties")
    @patch("uipath._cli._telemetry.track_cli_event")
    @patch("uipath._cli._telemetry.is_telemetry_enabled", return_value=True)
    def test_command_exception_propagates_when_telemetry_fails(
        self, mock_enabled, mock_track_event, mock_enrich
    ):
        mock_track_event.side_effect = Exception("Telemetry failed")

        @track_command("run")
        def my_command():
            raise ValueError("Command error")

        with pytest.raises(ValueError, match="Command error"):
            my_command()
