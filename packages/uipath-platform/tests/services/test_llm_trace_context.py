"""Tests for build_trace_context_headers."""

import os
from unittest.mock import patch

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
from uipath.core.feature_flags import FeatureFlags

from uipath.platform.chat.llm_trace_context import build_trace_context_headers
from uipath.platform.common.constants import ENV_PROJECT_KEY

FEATURE_FLAG = "EnableTraceContextHeaders"


def _make_span():
    """Create a real OTEL span for testing."""
    provider = TracerProvider()
    tracer = provider.get_tracer("test")
    return tracer.start_span("test-span")


class TestFeatureFlagDisabled:
    """When the feature flag is off, no headers are returned."""

    def setup_method(self) -> None:
        FeatureFlags.reset_flags()

    def test_returns_empty_dict_by_default(self) -> None:
        assert build_trace_context_headers() == {}

    def test_returns_empty_dict_when_explicitly_disabled(self) -> None:
        FeatureFlags.configure_flags({FEATURE_FLAG: False})
        assert build_trace_context_headers() == {}


class TestTraceparentHeader:
    """When enabled, x-uipath-traceparent-id is populated from config + span."""

    def setup_method(self) -> None:
        FeatureFlags.reset_flags()
        FeatureFlags.configure_flags({FEATURE_FLAG: True})

    def test_traceparent_from_config_and_span(self) -> None:
        span = _make_span()
        ctx = span.get_span_context()
        expected_span_id = format(ctx.span_id, "032x")
        config_trace = "abcdef1234567890abcdef1234567890"
        env = {"UIPATH_TRACE_ID": config_trace}
        with (
            patch.dict(os.environ, env),
            patch(
                "uipath.platform.chat.llm_trace_context.trace.get_current_span",
                return_value=span,
            ),
        ):
            headers = build_trace_context_headers()

        assert "x-uipath-traceparent-id" in headers
        value = headers["x-uipath-traceparent-id"]
        assert value == f"00-{config_trace}-{expected_span_id}"
        parts = value.split("-")
        assert len(parts) == 3
        assert parts[0] == "00"
        assert len(parts[1]) == 32
        assert len(parts[2]) == 32

    def test_no_traceparent_without_config_trace_id(self) -> None:
        headers = build_trace_context_headers()
        assert "x-uipath-traceparent-id" not in headers

    def test_traceparent_strips_dashes_from_config_trace_id(self) -> None:
        span = _make_span()
        uuid_trace = "abcdef12-3456-7890-abcd-ef1234567890"
        env = {"UIPATH_TRACE_ID": uuid_trace}
        with (
            patch.dict(os.environ, env),
            patch(
                "uipath.platform.chat.llm_trace_context.trace.get_current_span",
                return_value=span,
            ),
        ):
            headers = build_trace_context_headers()

        value = headers["x-uipath-traceparent-id"]
        parts = value.split("-")
        assert parts[1] == "abcdef1234567890abcdef1234567890"

    def test_no_traceparent_with_invalid_span(self) -> None:
        ctx = SpanContext(
            trace_id=0,
            span_id=0,
            is_remote=False,
            trace_flags=TraceFlags(0),
        )
        span = NonRecordingSpan(ctx)
        env = {"UIPATH_TRACE_ID": "abcdef1234567890abcdef1234567890"}
        with (
            patch.dict(os.environ, env),
            patch(
                "uipath.platform.chat.llm_trace_context.trace.get_current_span",
                return_value=span,
            ),
        ):
            headers = build_trace_context_headers()

        assert "x-uipath-traceparent-id" not in headers


class TestBaggageHeader:
    """When enabled, x-uipath-tracebaggage is populated from UiPathConfig."""

    def setup_method(self) -> None:
        from uipath.platform.common._span_utils import _read_config_id

        _read_config_id.cache_clear()
        FeatureFlags.reset_flags()
        FeatureFlags.configure_flags({FEATURE_FLAG: True})

    def test_all_env_vars_present(self) -> None:
        env = {
            "UIPATH_FOLDER_KEY": "folder-abc",
            ENV_PROJECT_KEY: "agent-123",
            "UIPATH_PROCESS_KEY": "process-789",
        }
        with patch.dict(os.environ, env, clear=True):
            headers = build_trace_context_headers()

        baggage = headers["x-uipath-tracebaggage"]
        assert "folderKey=folder-abc" in baggage
        assert "agentId=agent-123" in baggage
        assert "processKey=process-789" in baggage

    def test_partial_env_vars(self) -> None:
        env = {"UIPATH_FOLDER_KEY": "folder-only"}
        with patch.dict(os.environ, env, clear=True):
            headers = build_trace_context_headers()

        baggage = headers["x-uipath-tracebaggage"]
        assert "folderKey=folder-only" in baggage

    def test_agent_id_from_project_key_env(self) -> None:
        env = {ENV_PROJECT_KEY: "real-agent-id"}
        with patch.dict(os.environ, env, clear=True):
            headers = build_trace_context_headers()

        baggage = headers["x-uipath-tracebaggage"]
        assert "agentId=real-agent-id" in baggage

    def test_no_agent_id_without_env_vars(self) -> None:
        env = {"UIPATH_FOLDER_KEY": "f1"}
        with patch.dict(os.environ, env, clear=True):
            headers = build_trace_context_headers()

        baggage = headers["x-uipath-tracebaggage"]
        assert "agentId" not in baggage
        assert "folderKey=f1" in baggage

    def test_no_baggage_without_env_vars(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            headers = build_trace_context_headers()

        assert "x-uipath-tracebaggage" not in headers

    def test_baggage_comma_separated(self) -> None:
        env = {
            "UIPATH_FOLDER_KEY": "f1",
            ENV_PROJECT_KEY: "a1",
        }
        with patch.dict(os.environ, env, clear=True):
            headers = build_trace_context_headers()

        baggage = headers["x-uipath-tracebaggage"]
        parts = baggage.split(",")
        assert len(parts) == 2  # folderKey + agentId

    def test_extra_baggage_included(self) -> None:
        env = {"UIPATH_FOLDER_KEY": "f1"}
        with patch.dict(os.environ, env, clear=True):
            headers = build_trace_context_headers(extra_baggage=["source=agents"])

        baggage = headers["x-uipath-tracebaggage"]
        assert "source=agents" in baggage
        assert "folderKey=f1" in baggage

    def test_extra_baggage_only(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            headers = build_trace_context_headers(
                extra_baggage=["source=agents", "custom=value"]
            )

        baggage = headers["x-uipath-tracebaggage"]
        assert baggage == "source=agents,custom=value"


class TestBothHeaders:
    """When enabled with an active span and env vars, both headers are present."""

    def setup_method(self) -> None:
        FeatureFlags.reset_flags()
        FeatureFlags.configure_flags({FEATURE_FLAG: True})

    def test_both_headers_present(self) -> None:
        span = _make_span()
        env = {
            "UIPATH_FOLDER_KEY": "folder-abc",
            "UIPATH_TRACE_ID": "abcdef1234567890abcdef1234567890",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch(
                "uipath.platform.chat.llm_trace_context.trace.get_current_span",
                return_value=span,
            ),
        ):
            headers = build_trace_context_headers()

        assert "x-uipath-traceparent-id" in headers
        assert headers["x-uipath-traceparent-id"].startswith(
            "00-abcdef1234567890abcdef1234567890-"
        )
        assert "x-uipath-tracebaggage" in headers
