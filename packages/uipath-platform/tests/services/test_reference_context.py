"""Tests for ReferenceContext, ReferenceContextAccessor, and span Context wiring."""

import json
from datetime import datetime
from unittest.mock import Mock

import pytest
from opentelemetry.sdk.trace import Span as OTelSpan
from opentelemetry.trace import SpanContext, StatusCode

from uipath.platform.common import _SpanUtils
from uipath.platform.common._reference_context import (
    ReferenceContext,
    ReferenceContextAccessor,
    ReferenceEntry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_span(attributes: dict | None = None) -> Mock:
    mock = Mock(spec=OTelSpan)
    mock.get_span_context.return_value = SpanContext(
        trace_id=0x123456789ABCDEF0123456789ABCDEF0,
        span_id=0x0123456789ABCDEF,
        is_remote=False,
    )
    mock.name = "test-span"
    mock.parent = None
    mock.status.status_code = StatusCode.OK
    mock.attributes = attributes or {}
    mock.events = []
    mock.links = []
    now_ns = int(datetime.now().timestamp() * 1e9)
    mock.start_time = now_ns
    mock.end_time = now_ns + 1_000_000
    return mock


# ---------------------------------------------------------------------------
# ReferenceContext — immutability & copy-on-write
# ---------------------------------------------------------------------------

class TestReferenceContextImmutability:
    def test_empty_singleton_is_falsy(self) -> None:
        assert not ReferenceContext.Empty

    def test_add_returns_new_instance(self) -> None:
        base = ReferenceContext.Empty
        child = base.add("agent", "550e8400-e29b-41d4-a716-446655440001")
        assert child is not base

    def test_original_unmodified_after_add(self) -> None:
        base = ReferenceContext.Empty
        base.add("agent", "550e8400-e29b-41d4-a716-446655440001")
        assert len(base) == 0

    def test_siblings_do_not_share_entries(self) -> None:
        base = ReferenceContext.Empty.add("maestro", "550e8400-e29b-41d4-a716-446655440010", "2.0")
        child_a = base.add("agent", "550e8400-e29b-41d4-a716-446655440011")
        child_b = base.add("agent", "550e8400-e29b-41d4-a716-446655440012")

        assert len(base) == 1
        assert len(child_a) == 2
        assert len(child_b) == 2
        assert child_a.entries[1].reference_id != child_b.entries[1].reference_id

    def test_equality_and_hash(self) -> None:
        a = ReferenceContext.Empty.add("agent", "550e8400-e29b-41d4-a716-446655440001")
        b = ReferenceContext.Empty.add("agent", "550e8400-e29b-41d4-a716-446655440001")
        assert a == b
        assert hash(a) == hash(b)

    def test_different_entries_not_equal(self) -> None:
        a = ReferenceContext.Empty.add("agent", "550e8400-e29b-41d4-a716-446655440001")
        b = ReferenceContext.Empty.add("agent", "550e8400-e29b-41d4-a716-446655440002")
        assert a != b


# ---------------------------------------------------------------------------
# ReferenceContext.add — validation & UUID coercion
# ---------------------------------------------------------------------------

class TestReferenceContextAdd:
    def test_add_with_string_uuid(self) -> None:
        ctx = ReferenceContext.Empty.add("agent", "550e8400-e29b-41d4-a716-446655440001", "1.0")
        assert len(ctx) == 1
        e = ctx.entries[0]
        assert e.service_type == "agent"
        assert e.reference_id == "550e8400-e29b-41d4-a716-446655440001"
        assert e.version == "1.0"

    def test_add_with_uuid_object(self) -> None:
        import uuid
        uid = uuid.UUID("550e8400-e29b-41d4-a716-446655440001")
        ctx = ReferenceContext.Empty.add("agent", uid)
        assert ctx.entries[0].reference_id == str(uid)

    def test_add_without_version(self) -> None:
        ctx = ReferenceContext.Empty.add("agent", "550e8400-e29b-41d4-a716-446655440001")
        assert ctx.entries[0].version is None

    def test_add_blank_version_normalised_to_none(self) -> None:
        ctx = ReferenceContext.Empty.add("agent", "550e8400-e29b-41d4-a716-446655440001", "  ")
        assert ctx.entries[0].version is None

    def test_add_empty_service_type_raises(self) -> None:
        with pytest.raises(ValueError, match="service_type"):
            ReferenceContext.Empty.add("", "550e8400-e29b-41d4-a716-446655440001")

    def test_add_invalid_reference_id_type_raises(self) -> None:
        with pytest.raises(TypeError, match="reference_id"):
            ReferenceContext.Empty.add("agent", 12345)  # type: ignore[arg-type]

    def test_entries_ordered_oldest_first(self) -> None:
        ctx = (
            ReferenceContext.Empty
            .add("maestro", "550e8400-e29b-41d4-a716-446655440010", "2.0")
            .add("agent", "550e8400-e29b-41d4-a716-446655440011")
        )
        assert ctx.entries[0].service_type == "maestro"
        assert ctx.entries[1].service_type == "agent"


# ---------------------------------------------------------------------------
# ReferenceContext.to_wire_list
# ---------------------------------------------------------------------------

class TestToWireList:
    def test_empty_produces_empty_list(self) -> None:
        assert ReferenceContext.Empty.to_wire_list() == []

    def test_single_entry_with_version(self) -> None:
        ctx = ReferenceContext.Empty.add("agent", "550e8400-e29b-41d4-a716-446655440001", "1.0.0")
        wire = ctx.to_wire_list()
        assert wire == [
            {"serviceType": "agent", "referenceId": "550e8400-e29b-41d4-a716-446655440001", "version": "1.0.0"}
        ]

    def test_single_entry_without_version_omits_key(self) -> None:
        ctx = ReferenceContext.Empty.add("agent", "550e8400-e29b-41d4-a716-446655440001")
        wire = ctx.to_wire_list()
        assert "version" not in wire[0]

    def test_multiple_entries_order_preserved(self) -> None:
        ctx = (
            ReferenceContext.Empty
            .add("maestro", "550e8400-e29b-41d4-a716-446655440010", "2.1.0")
            .add("agent", "550e8400-e29b-41d4-a716-446655440011")
        )
        wire = ctx.to_wire_list()
        assert len(wire) == 2
        assert wire[0]["serviceType"] == "maestro"
        assert wire[0]["version"] == "2.1.0"
        assert wire[1]["serviceType"] == "agent"
        assert "version" not in wire[1]


# ---------------------------------------------------------------------------
# ReferenceContext.from_baggage_header / to_baggage_header_value round-trip
# ---------------------------------------------------------------------------

class TestBaggageHeaderRoundTrip:
    def test_round_trip_single_entry_with_version(self) -> None:
        ctx = ReferenceContext.Empty.add("agent", "550e8400-e29b-41d4-a716-446655440001", "1.0")
        assert ReferenceContext.from_baggage_header(ctx.to_baggage_header_value()) == ctx

    def test_round_trip_multiple_entries(self) -> None:
        ctx = (
            ReferenceContext.Empty
            .add("maestro", "550e8400-e29b-41d4-a716-446655440010", "2.0")
            .add("agent", "550e8400-e29b-41d4-a716-446655440011")
        )
        assert ReferenceContext.from_baggage_header(ctx.to_baggage_header_value()) == ctx

    def test_empty_header_returns_empty(self) -> None:
        assert ReferenceContext.from_baggage_header("") == ReferenceContext.Empty
        assert ReferenceContext.from_baggage_header(None) == ReferenceContext.Empty

    def test_malformed_entry_skipped_silently(self) -> None:
        # Only the second entry is valid
        header = "not-a-valid-entry,ref.type=agent;ref.id=550e8400-e29b-41d4-a716-446655440001"
        ctx = ReferenceContext.from_baggage_header(header)
        assert len(ctx) == 1
        assert ctx.entries[0].service_type == "agent"

    def test_entry_with_invalid_uuid_skipped(self) -> None:
        header = "ref.type=agent;ref.id=not-a-uuid"
        ctx = ReferenceContext.from_baggage_header(header)
        assert ctx == ReferenceContext.Empty

    def test_entry_missing_type_skipped(self) -> None:
        header = "ref.id=550e8400-e29b-41d4-a716-446655440001"
        ctx = ReferenceContext.from_baggage_header(header)
        assert ctx == ReferenceContext.Empty

    def test_empty_context_produces_empty_header(self) -> None:
        assert ReferenceContext.Empty.to_baggage_header_value() == ""


# ---------------------------------------------------------------------------
# ReferenceContextAccessor — ContextVar semantics
# ---------------------------------------------------------------------------

class TestReferenceContextAccessor:
    def setup_method(self) -> None:
        # Ensure clean state before each test
        current = ReferenceContextAccessor.get()
        if current is not None:
            token = ReferenceContextAccessor.set(None)
            # immediately reset to avoid polluting other tests
            ReferenceContextAccessor.reset(token)

    def test_default_is_none(self) -> None:
        assert ReferenceContextAccessor.get() is None

    def test_set_and_get(self) -> None:
        ctx = ReferenceContext.Empty.add("agent", "550e8400-e29b-41d4-a716-446655440001")
        token = ReferenceContextAccessor.set(ctx)
        try:
            assert ReferenceContextAccessor.get() == ctx
        finally:
            ReferenceContextAccessor.reset(token)

    def test_reset_restores_prior_value(self) -> None:
        ctx_a = ReferenceContext.Empty.add("agent", "550e8400-e29b-41d4-a716-446655440001")
        ctx_b = ctx_a.add("langgraph", "550e8400-e29b-41d4-a716-446655440002")

        token_a = ReferenceContextAccessor.set(ctx_a)
        token_b = ReferenceContextAccessor.set(ctx_b)

        assert ReferenceContextAccessor.get() == ctx_b
        ReferenceContextAccessor.reset(token_b)
        assert ReferenceContextAccessor.get() == ctx_a
        ReferenceContextAccessor.reset(token_a)
        assert ReferenceContextAccessor.get() is None


# ---------------------------------------------------------------------------
# UiPathSpan.context wiring via otel_span_to_uipath_span
# ---------------------------------------------------------------------------

class TestContextWiring:
    def test_context_absent_when_no_reference_context_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UIPATH_ORGANIZATION_ID", "test-org")
        # Ensure accessor is clear
        token = ReferenceContextAccessor.set(None)
        try:
            span = _SpanUtils.otel_span_to_uipath_span(_make_mock_span())
            assert span.context is None
            assert "Context" not in span.to_dict()
        finally:
            ReferenceContextAccessor.reset(token)

    def test_context_present_when_reference_context_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UIPATH_ORGANIZATION_ID", "test-org")
        ref_ctx = ReferenceContext.Empty.add(
            "agent", "550e8400-e29b-41d4-a716-446655440001", "1.0"
        )
        token = ReferenceContextAccessor.set(ref_ctx)
        try:
            span = _SpanUtils.otel_span_to_uipath_span(_make_mock_span())
            assert span.context == {
                "referenceHierarchy": [
                    {
                        "serviceType": "agent",
                        "referenceId": "550e8400-e29b-41d4-a716-446655440001",
                        "version": "1.0",
                    }
                ]
            }
            wire = span.to_dict()
            assert "Context" in wire
            assert wire["Context"]["referenceHierarchy"][0]["serviceType"] == "agent"
        finally:
            ReferenceContextAccessor.reset(token)

    def test_context_carries_full_hierarchy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("UIPATH_ORGANIZATION_ID", "test-org")
        ref_ctx = (
            ReferenceContext.Empty
            .add("maestro", "550e8400-e29b-41d4-a716-446655440010", "2.0")
            .add("agent", "550e8400-e29b-41d4-a716-446655440011")
        )
        token = ReferenceContextAccessor.set(ref_ctx)
        try:
            wire = _SpanUtils.otel_span_to_uipath_span(_make_mock_span()).to_dict()
            hierarchy = wire["Context"]["referenceHierarchy"]
            assert len(hierarchy) == 2
            assert hierarchy[0]["serviceType"] == "maestro"
            assert hierarchy[0]["version"] == "2.0"
            assert hierarchy[1]["serviceType"] == "agent"
            assert "version" not in hierarchy[1]
        finally:
            ReferenceContextAccessor.reset(token)
