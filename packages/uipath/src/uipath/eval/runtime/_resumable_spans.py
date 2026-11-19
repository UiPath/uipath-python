"""Eval spans that outlive a suspended job and are finished by the resuming one."""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, cast

from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Tracer, TracerProvider
from opentelemetry.sdk.trace.id_generator import IdGenerator
from opentelemetry.trace import (
    NonRecordingSpan,
    Span,
    SpanContext,
    TraceFlags,
    set_span_in_context,
    use_span,
)

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
    saved = await _load(storage, runtime_id, key) if resume else None
    span_cm = (
        use_span(
            _reopen(cast(Tracer, tracer), saved, name, attributes), end_on_exit=True
        )
        if saved
        else tracer.start_as_current_span(name, attributes=attributes)
    )
    with span_cm as span:
        await _save(storage, runtime_id, key, span)
        yield span


# The trace backend upserts by span id, so this replaces the suspended job's output.
def _reopen(
    tracer: Tracer, saved: dict[str, Any], name: str, attributes: dict[str, Any]
) -> Span:
    original_generator = tracer.id_generator
    tracer.id_generator = _SavedIdGenerator(
        int(saved["trace_id"], 16), int(saved["span_id"], 16)
    )
    try:
        return tracer.start_span(
            name,
            context=_parent_context(saved),
            attributes=attributes,
            start_time=saved.get("start_time"),
        )
    finally:
        tracer.id_generator = original_generator


def _parent_context(saved: dict[str, Any]) -> Context | None:
    # Records saved before "parent" existed fall back to the current context.
    if "parent" not in saved:
        return None
    parent = saved["parent"]
    if parent is None:
        return Context()
    return set_span_in_context(
        NonRecordingSpan(
            SpanContext(
                trace_id=int(parent["trace_id"], 16),
                span_id=int(parent["span_id"], 16),
                is_remote=True,
                trace_flags=TraceFlags(TraceFlags.SAMPLED),
            )
        )
    )


async def _load(
    storage: UiPathRuntimeStorageProtocol | None, runtime_id: str, key: str
) -> dict[str, Any] | None:
    if storage is None:
        return None
    saved = await storage.get_value(
        runtime_id=runtime_id, namespace=_NAMESPACE, key=key
    )
    # Zero ids were written for invalid spans (SDK disabled) before _save skipped them.
    if not saved or int(saved["trace_id"], 16) == 0:
        return None
    return saved


async def _save(
    storage: UiPathRuntimeStorageProtocol | None,
    runtime_id: str,
    key: str,
    span: Span,
) -> None:
    if storage is None:
        return
    span_context = span.get_span_context()
    if not span_context.is_valid:
        return
    # Absent on a NonRecordingSpan, e.g. one the sampler dropped.
    parent = getattr(cast(ReadableSpan, span), "parent", None)
    await storage.set_value(
        runtime_id=runtime_id,
        namespace=_NAMESPACE,
        key=key,
        value={
            **_hex_ids(span_context),
            "start_time": getattr(cast(ReadableSpan, span), "start_time", None),
            "parent": _hex_ids(parent) if parent else None,
        },
    )


def _hex_ids(span_context: SpanContext) -> dict[str, str]:
    return {
        "trace_id": format(span_context.trace_id, "032x"),
        "span_id": format(span_context.span_id, "016x"),
    }
