from asyncio import sleep
from typing import List, Sequence

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

from uipath.tracing._traced import traced


class InMemorySpanExporter(SpanExporter):
    """An OpenTelemetry span exporter that stores spans in memory for testing."""

    def __init__(self):
        self.spans = []
        self.is_shutdown = False

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if self.is_shutdown:
            return SpanExportResult.FAILURE

        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def get_exported_spans(self) -> List[ReadableSpan]:
        return self.spans

    def clear_exported_spans(self) -> None:
        self.spans = []

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return not self.is_shutdown

    def shutdown(self) -> None:
        self.is_shutdown = True


@pytest.fixture
def setup_tracer():
    # Setup InMemorySpanExporter and TracerProvider
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(exporter))  # type: ignore

    yield exporter, provider


def test_traced_sync_function(setup_tracer):
    exporter, provider = setup_tracer

    @traced()
    def sample_function(x, y):
        return x + y

    result = sample_function(2, 3)
    assert result == 5

    provider.shutdown()  # Ensure spans are flushed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]
    assert span.name == "sample_function"
    assert span.attributes["span_type"] == "function_call_sync"
    assert "inputs" in span.attributes
    assert "output" in span.attributes
    assert span.attributes["output"] == "5"


@pytest.mark.asyncio
async def test_traced_async_function(setup_tracer):
    exporter, provider = setup_tracer

    @traced()
    async def sample_async_function(x, y):
        return x * y

    result = await sample_async_function(2, 3)
    assert result == 6

    provider.shutdown()  # Ensure spans are flushed

    await sleep(1)
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]
    assert span.name == "sample_async_function"
    assert span.attributes["span_type"] == "function_call_async"
    assert "inputs" in span.attributes
    assert "output" in span.attributes
    assert span.attributes["output"] == "6"


def test_traced_generator_function(setup_tracer):
    exporter, provider = setup_tracer

    @traced()
    def sample_generator_function(n):
        for i in range(n):
            yield i

    results = list(sample_generator_function(3))
    assert results == [0, 1, 2]

    provider.shutdown()  # Ensure spans are flushed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]
    assert span.name == "sample_generator_function"
    assert span.attributes["span_type"] == "function_call_generator_sync"
    assert "inputs" in span.attributes
    assert "output" in span.attributes
    assert span.attributes["output"] == "[0, 1, 2]"


@pytest.mark.asyncio
async def test_traced_async_generator_function(setup_tracer):
    exporter, provider = setup_tracer

    @traced()
    async def sample_async_generator_function(n):
        for i in range(n):
            yield i

    results = [item async for item in sample_async_generator_function(3)]
    assert results == [0, 1, 2]

    provider.shutdown()  # Ensure spans are flushed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]
    assert span.name == "sample_async_generator_function"
    assert span.attributes["span_type"] == "function_call_generator_async"
    assert "inputs" in span.attributes
    assert "output" in span.attributes
    assert span.attributes["output"] == "[0, 1, 2]"
