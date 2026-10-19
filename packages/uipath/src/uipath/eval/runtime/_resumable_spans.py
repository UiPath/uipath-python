"""Eval spans that outlive a suspended job and are finished by the resuming one."""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, cast

from opentelemetry.sdk.trace import ReadableSpan, Tracer, TracerProvider
from opentelemetry.sdk.trace.id_generator import IdGenerator
from opentelemetry.trace import Span

from uipath.runtime import UiPathRuntimeStorageProtocol

_NAMESPACE = "eval_parent_span"


class _SavedIdGenerator(IdGenerator):
    def __init__(self, trace_id: int, span_id: int) -> None:
        self._trace_id = trace_id
        self._span_id = span_id

    def generate_trace_id(self) -> int:
        return self._trace_id

    def generate_span_id(self) -> int:
        return self._span_id


@asynccontextmanager
async def start_resumable_span(
    tracer_provider: TracerProvider,
    storage: UiPathRuntimeStorageProtocol | None,
    runtime_id: str,
    key: str,
    *,
    resume: bool,
    name: str,
    attributes: dict[str, Any],
) -> AsyncIterator[Span]:
    """Start a span, or on resume re-open the one the suspended job saved under `key`."""
    tracer = tracer_provider.get_tracer(__name__)
    start_time = None
    saved = await _load(storage, runtime_id, key) if resume else None
    # The trace backend upserts by span id, so this replaces the suspended job's output.
    if saved:
        cast(Tracer, tracer).id_generator = _SavedIdGenerator(
            int(saved["trace_id"], 16), int(saved["span_id"], 16)
        )
        start_time = saved.get("start_time")

    with tracer.start_as_current_span(
        name, attributes=attributes, start_time=start_time
    ) as span:
        await _save(storage, runtime_id, key, span)
        yield span


async def _load(
    storage: UiPathRuntimeStorageProtocol | None, runtime_id: str, key: str
) -> dict[str, Any] | None:
    if storage is None:
        return None
    return await storage.get_value(runtime_id=runtime_id, namespace=_NAMESPACE, key=key)


async def _save(
    storage: UiPathRuntimeStorageProtocol | None,
    runtime_id: str,
    key: str,
    span: Span,
) -> None:
    if storage is None:
        return
    span_context = span.get_span_context()
    await storage.set_value(
        runtime_id=runtime_id,
        namespace=_NAMESPACE,
        key=key,
        value={
            "trace_id": format(span_context.trace_id, "032x"),
            "span_id": format(span_context.span_id, "016x"),
            # Absent on a NonRecordingSpan (SDK disabled).
            "start_time": getattr(cast(ReadableSpan, span), "start_time", None),
        },
    )
