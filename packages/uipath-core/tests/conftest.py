"""Shared pytest fixtures for all tests."""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


class SpanCapture:
    """Helper to capture and analyze spans."""

    def __init__(self):
        self.exporter = InMemorySpanExporter()
        self.provider = TracerProvider()
        self.provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        trace.set_tracer_provider(self.provider)

    def get_spans(self):
        """Get all captured spans."""
        return self.exporter.get_finished_spans()

    def clear(self):
        """Clear captured spans."""
        self.exporter.clear()

    def print_hierarchy(self):
        """Print the span hierarchy for debugging."""
        spans = self.get_spans()
        print("\n=== Span Hierarchy ===")
        for span in spans:
            parent_id = span.parent.span_id if span.parent else "ROOT"
            print(f"  {span.name}")
            print(f"    Span ID: {span.context.span_id}")
            print(f"    Parent ID: {parent_id}")
            print(f"    Trace ID: {span.context.trace_id}")
        print("======================\n")


@pytest.fixture(scope="session")
def span_capture() -> SpanCapture:
    """Fixture to capture spans - created once for entire test session."""
    return SpanCapture()


@pytest.fixture(autouse=True)
def clear_spans_between_tests(span_capture: SpanCapture):
    """Clear captured spans before each test."""
    span_capture.clear()
    yield
