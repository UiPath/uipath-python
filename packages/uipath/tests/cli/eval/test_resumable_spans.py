from typing import Any, cast

from opentelemetry.sdk.trace import Tracer, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from uipath.eval.runtime._resumable_spans import start_resumable_span

SAVED_TRACE_ID = "0123456789abcdef0123456789abcdef"
SAVED_SPAN_ID = "0123456789abcdef"


class DictStorage:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        self.values = values or {}

    async def set_value(
        self, runtime_id: str, namespace: str, key: str, value: Any
    ) -> None:
        self.values[key] = value

    async def get_value(self, runtime_id: str, namespace: str, key: str) -> Any:
        return self.values.get(key)


class CachingProvider(TracerProvider):
    def __init__(self) -> None:
        super().__init__()
        self.tracer = cast(Tracer, super().get_tracer("cached"))

    def get_tracer(self, *args: Any, **kwargs: Any) -> Tracer:
        return self.tracer


async def _resume(
    provider: TracerProvider, saved: dict[str, Any]
) -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    async with start_resumable_span(
        provider,
        DictStorage({"k": saved}),
        "run",
        "k",
        resume=True,
        name="Evaluation",
        attributes={},
    ):
        pass
    return exporter


async def test_reopening_leaves_a_cached_tracers_id_generator_alone():
    provider = CachingProvider()
    original = provider.tracer.id_generator

    await _resume(
        provider,
        {"trace_id": SAVED_TRACE_ID, "span_id": SAVED_SPAN_ID, "parent": None},
    )

    assert provider.tracer.id_generator is original


async def test_record_saved_without_parent_still_reopens_the_saved_span():
    exporter = await _resume(
        TracerProvider(), {"trace_id": SAVED_TRACE_ID, "span_id": SAVED_SPAN_ID}
    )

    (span,) = exporter.get_finished_spans()
    assert span.context is not None
    assert format(span.context.span_id, "016x") == SAVED_SPAN_ID
    assert format(span.context.trace_id, "032x") == SAVED_TRACE_ID


async def test_record_with_zero_ids_starts_a_fresh_span():
    exporter = await _resume(
        TracerProvider(), {"trace_id": "0" * 32, "span_id": "0" * 16, "parent": None}
    )

    (span,) = exporter.get_finished_spans()
    assert span.context is not None and span.context.is_valid
