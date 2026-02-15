"""Reconstructed span that duck-types the OpenTelemetry ReadableSpan interface.

Used on the remote evaluation worker side to rebuild spans from serialized data
so that existing evaluators can consume them without code changes.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Sequence

from uipath.eval.models.serializable_span import SerializableSpan


class _ReconstructedStatus:
    """Mimics opentelemetry.trace.Status for reconstructed spans."""

    def __init__(self, status_code_value: int, description: str | None = None):
        self._status_code = _ReconstructedStatusCode(status_code_value)
        self._description = description

    @property
    def status_code(self) -> "_ReconstructedStatusCode":
        return self._status_code

    @property
    def description(self) -> str | None:
        return self._description


class _ReconstructedStatusCode:
    """Mimics opentelemetry.trace.StatusCode enum values."""

    UNSET = 0
    OK = 1
    ERROR = 2

    def __init__(self, value: int):
        self._value = value

    @property
    def value(self) -> int:
        return self._value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _ReconstructedStatusCode):
            return self._value == other._value
        if isinstance(other, int):
            return self._value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)


class _ReconstructedSpanContext:
    """Mimics opentelemetry.trace.SpanContext."""

    def __init__(self, trace_id: int, span_id: int):
        self._trace_id = trace_id
        self._span_id = span_id

    @property
    def trace_id(self) -> int:
        return self._trace_id

    @property
    def span_id(self) -> int:
        return self._span_id

    @property
    def trace_flags(self) -> int:
        return 0x01  # Sampled

    @property
    def trace_state(self) -> None:
        return None

    @property
    def is_valid(self) -> bool:
        return self._trace_id != 0 and self._span_id != 0


class _ReconstructedEvent:
    """Mimics opentelemetry.sdk.trace.Event."""

    def __init__(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        timestamp: int | None = None,
    ):
        self._name = name
        self._attributes = MappingProxyType(attributes or {})
        self._timestamp = timestamp

    @property
    def name(self) -> str:
        return self._name

    @property
    def attributes(self) -> MappingProxyType[str, Any]:
        return self._attributes

    @property
    def timestamp(self) -> int | None:
        return self._timestamp


class ReconstructedSpan:
    """A span reconstructed from SerializableSpan data.

    Implements the same interface as opentelemetry.sdk.trace.ReadableSpan
    (duck-typing) so that evaluators that expect ReadableSpan can work
    with reconstructed spans without modification.
    """

    def __init__(self, data: SerializableSpan):
        self._data = data

        # Parse hex IDs into integers
        self._trace_id = int(data.trace_id, 16) if data.trace_id else 0
        self._span_id = int(data.span_id, 16) if data.span_id else 0

        # Build span context
        self._context = _ReconstructedSpanContext(self._trace_id, self._span_id)

        # Build parent context
        self._parent: _ReconstructedSpanContext | None = None
        if data.parent_span_id:
            parent_span_id = int(data.parent_span_id, 16)
            self._parent = _ReconstructedSpanContext(self._trace_id, parent_span_id)

        # Build status
        status_map = {"unset": 0, "ok": 1, "error": 2}
        status_code_value = status_map.get(data.status, 0)
        self._status = _ReconstructedStatus(status_code_value, data.status_description)

        # Build attributes as MappingProxy (matching ReadableSpan behavior)
        self._attributes: MappingProxyType[str, Any] = MappingProxyType(
            data.attributes
        )

        # Build events
        self._events: tuple[_ReconstructedEvent, ...] = tuple(
            _ReconstructedEvent(
                name=e.name,
                attributes=e.attributes,
                timestamp=e.timestamp,
            )
            for e in data.events
        )

    @property
    def name(self) -> str:
        return self._data.name

    @property
    def start_time(self) -> int | None:
        return self._data.start_time_unix_nano or None

    @property
    def end_time(self) -> int | None:
        return self._data.end_time_unix_nano or None

    @property
    def attributes(self) -> MappingProxyType[str, Any]:
        return self._attributes

    @property
    def events(self) -> Sequence[_ReconstructedEvent]:
        return self._events

    @property
    def status(self) -> _ReconstructedStatus:
        return self._status

    @property
    def parent(self) -> _ReconstructedSpanContext | None:
        return self._parent

    def get_span_context(self) -> _ReconstructedSpanContext:
        return self._context

    @property
    def resource(self) -> None:
        return None

    @property
    def instrumentation_info(self) -> None:
        return None

    @property
    def links(self) -> tuple[()]:
        return ()

    @classmethod
    def from_serializable_spans(
        cls, spans: list[SerializableSpan]
    ) -> list["ReconstructedSpan"]:
        """Convert a list of SerializableSpans to ReconstructedSpans.

        Args:
            spans: List of SerializableSpan instances.

        Returns:
            List of ReconstructedSpan instances.
        """
        return [cls(s) for s in spans]
