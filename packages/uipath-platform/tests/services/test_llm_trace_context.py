"""Tests for build_trace_context_headers."""

import os
from unittest.mock import patch

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
from uipath.core.feature_flags import FeatureFlags

from uipath.platform.chat.llm_trace_context import build_trace_context_headers

FEATURE_FLAG = "EnableTraceContextHeaders"


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
    """When enabled, x-uipath-traceparent-id is populated from the active span."""

    def setup_method(self) -> None:
        FeatureFlags.reset_flags()
        FeatureFlags.configure_flags({FEATURE_FLAG: True})

    def test_traceparent_from_active_span(self) -> None:
        provider = TracerProvider()
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("test-span") as span:
            ctx = span.get_span_context()
            expected_trace_id = format(ctx.trace_id, "032x")
            expected_span_id = format(ctx.span_id, "016x")

            headers = build_trace_context_headers()

        assert "x-uipath-traceparent-id" in headers
        value = headers["x-uipath-traceparent-id"]
        assert value == f"00-{expected_trace_id}-{expected_span_id}"
        # Verify format: version (2) + dash + trace_id (32) + dash + span_id (16)
        parts = value.split("-")
        assert len(parts) == 3
        assert parts[0] == "00"
        assert len(parts[1]) == 32
        assert len(parts[2]) == 16

    def test_no_traceparent_without_active_span(self) -> None:
        # INVALID_SPAN has trace_id=0 and span_id=0
        from opentelemetry.context import attach, detach

        ctx = SpanContext(
            trace_id=0,
            span_id=0,
            is_remote=False,
            trace_flags=TraceFlags(0),
        )
        non_recording = NonRecordingSpan(ctx)
        token = attach(trace.set_span_in_context(non_recording))
        try:
            headers = build_trace_context_headers()
        finally:
            detach(token)

        assert "x-uipath-traceparent-id" not in headers


class TestBaggageHeader:
    """When enabled, x-uipath-tracebaggage is populated from UiPathConfig."""

    def setup_method(self) -> None:
        FeatureFlags.reset_flags()
        FeatureFlags.configure_flags({FEATURE_FLAG: True})

    def test_all_env_vars_present(self) -> None:
        env = {
            "UIPATH_FOLDER_KEY": "folder-abc",
            "UIPATH_PROCESS_UUID": "agent-123",
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

    def test_no_baggage_without_env_vars(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            headers = build_trace_context_headers()

        assert "x-uipath-tracebaggage" not in headers

    def test_baggage_comma_separated(self) -> None:
        env = {
            "UIPATH_FOLDER_KEY": "f1",
            "UIPATH_PROCESS_UUID": "a1",
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
        provider = TracerProvider()
        tracer = provider.get_tracer("test")
        env = {"UIPATH_FOLDER_KEY": "folder-abc"}
        with (
            tracer.start_as_current_span("test-span"),
            patch.dict(os.environ, env, clear=True),
        ):
            headers = build_trace_context_headers()

        assert "x-uipath-traceparent-id" in headers
        assert "x-uipath-tracebaggage" in headers
