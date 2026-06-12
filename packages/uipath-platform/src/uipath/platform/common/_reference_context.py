"""Immutable reference-hierarchy context for span propagation.

Follows the same design as service-common BaggageContext:
- Immutable, copy-on-write — each mutating call returns a NEW instance so
  sibling spans cannot bleed context into each other.
- ContextVar-backed accessor — flows across await boundaries without
  threading the value through every function signature.
- Wire format compatible with the ``ref.*`` keys in ``x-uipath-tracebaggage``
  so context parsed by service-common middleware is understood here and
  vice-versa.
"""
from __future__ import annotations

import contextvars
import uuid
from dataclasses import dataclass
from typing import Iterator, List, Optional, Tuple


__all__ = [
    "ReferenceEntry",
    "ReferenceContext",
    "ReferenceContextAccessor",
    "BAGGAGE_HEADER_NAME",
    "BAGGAGE_KEY_TYPE",
    "BAGGAGE_KEY_ID",
    "BAGGAGE_KEY_VERSION",
]

BAGGAGE_HEADER_NAME = "x-uipath-tracebaggage"

# Key names — matches service-common ReferenceHierarchyKeys
BAGGAGE_KEY_TYPE = "ref.type"
BAGGAGE_KEY_ID = "ref.id"
BAGGAGE_KEY_VERSION = "ref.v"


@dataclass(frozen=True)
class ReferenceEntry:
    """A single node in the reference hierarchy call chain."""

    service_type: str
    reference_id: str  # UUID string
    version: Optional[str] = None


class ReferenceContext:
    """Immutable, copy-on-write ordered list of reference entries.

    Outermost caller first, current service appended last.
    Each mutating call returns a new instance — the original is never
    modified, preventing sibling spans from sharing context.

    Usage::

        ctx = ReferenceContext.Empty
        ctx = ctx.add("maestro", process_id, "2.1.0")
        ctx = ctx.add("agent", agent_id)
        token = ReferenceContextAccessor.set(ctx)
        try:
            ...
        finally:
            ReferenceContextAccessor.reset(token)
    """

    __slots__ = ("_entries",)

    def __init__(self, entries: Tuple[ReferenceEntry, ...] = ()) -> None:
        self._entries: Tuple[ReferenceEntry, ...] = entries

    @property
    def entries(self) -> Tuple[ReferenceEntry, ...]:
        return self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[ReferenceEntry]:
        return iter(self._entries)

    def __bool__(self) -> bool:
        return len(self._entries) > 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ReferenceContext):
            return NotImplemented
        return self._entries == other._entries

    def __hash__(self) -> int:
        return hash(self._entries)

    def add(
        self,
        service_type: str,
        reference_id: str | uuid.UUID,
        version: Optional[str] = None,
    ) -> "ReferenceContext":
        """Returns a new context with this entry appended (copy-on-write).

        Args:
            service_type: Identifier for the calling service (e.g. ``"agent"``,
                ``"maestro"``).
            reference_id: UUID of the referenced entity (UUID object or string).
            version: Optional version string.

        Returns:
            A new :class:`ReferenceContext` with the entry appended.
        """
        if not service_type or not service_type.strip():
            raise ValueError("service_type must be a non-empty string.")
        if isinstance(reference_id, uuid.UUID):
            id_str = str(reference_id)
        elif isinstance(reference_id, str):
            id_str = reference_id
        else:
            raise TypeError("reference_id must be a UUID or string.")
        entry = ReferenceEntry(
            service_type=service_type,
            reference_id=id_str,
            version=version if version and version.strip() else None,
        )
        return ReferenceContext(self._entries + (entry,))

    def to_wire_list(self) -> List[dict]:
        """Serialize to the ``referenceHierarchy`` wire format.

        Returns:
            A list of dicts suitable for JSON serialization as
            ``Context.referenceHierarchy`` in the span payload.
        """
        result = []
        for e in self._entries:
            item: dict = {
                "serviceType": e.service_type,
                "referenceId": e.reference_id,
            }
            if e.version:
                item["version"] = e.version
            result.append(item)
        return result

    @staticmethod
    def from_baggage_header(header_value: Optional[str]) -> "ReferenceContext":
        """Parse ``x-uipath-tracebaggage`` header value into a ReferenceContext.

        Only entries that carry the ``ref.*`` shape (type + valid UUID id) are
        included. Malformed or plain-KV entries are silently skipped so a bad
        header from an upstream service cannot crash this one.

        Args:
            header_value: Raw header string, e.g.
                ``"ref.type=agent;ref.id=<uuid>;ref.v=1.0,ref.type=maestro;ref.id=<uuid>"``

        Returns:
            Parsed :class:`ReferenceContext`, or :attr:`ReferenceContext.Empty`
            if the header is absent, empty, or contains no valid ref entries.
        """
        if not header_value or not header_value.strip():
            return ReferenceContext.Empty

        entries: List[ReferenceEntry] = []
        for raw_entry in header_value.split(","):
            entry_text = raw_entry.strip()
            if not entry_text:
                continue
            props: dict[str, str] = {}
            for raw_pair in entry_text.split(";"):
                pair_text = raw_pair.strip()
                eq = pair_text.find("=")
                if eq <= 0 or eq >= len(pair_text) - 1:
                    continue
                key = pair_text[:eq].strip()
                value = pair_text[eq + 1:].strip()
                if key and value:
                    props[key] = value

            type_v = props.get(BAGGAGE_KEY_TYPE)
            id_v = props.get(BAGGAGE_KEY_ID)
            if not type_v or not id_v:
                continue
            try:
                parsed_uuid = uuid.UUID(id_v)
            except (ValueError, AttributeError):
                continue
            entries.append(
                ReferenceEntry(
                    service_type=type_v,
                    reference_id=str(parsed_uuid),
                    version=props.get(BAGGAGE_KEY_VERSION) or None,
                )
            )

        if not entries:
            return ReferenceContext.Empty
        return ReferenceContext(tuple(entries))

    def to_baggage_header_value(self) -> str:
        """Serialize to ``x-uipath-tracebaggage`` header value.

        Returns:
            Comma-separated entries; each is a semicolon-separated list of
            ``key=value`` pairs. Empty context returns ``""``.
        """
        if not self._entries:
            return ""
        parts: List[str] = []
        for e in self._entries:
            kv = f"{BAGGAGE_KEY_TYPE}={e.service_type};{BAGGAGE_KEY_ID}={e.reference_id}"
            if e.version:
                kv += f";{BAGGAGE_KEY_VERSION}={e.version}"
            parts.append(kv)
        return ",".join(parts)


# Assigned after class body so ReferenceContext is fully bound.
ReferenceContext.Empty = ReferenceContext()  # type: ignore[attr-defined]


class ReferenceContextAccessor:
    """Ambient accessor for the current :class:`ReferenceContext`.

    Backed by :mod:`contextvars` so the value propagates across ``await``
    boundaries without being threaded through every call signature.

    Usage::

        token = ReferenceContextAccessor.set(ctx)
        try:
            ...  # code here sees ReferenceContextAccessor.get() == ctx
        finally:
            ReferenceContextAccessor.reset(token)
    """

    _current: contextvars.ContextVar[Optional[ReferenceContext]] = (
        contextvars.ContextVar("uipath_reference_context", default=None)
    )

    @classmethod
    def get(cls) -> Optional[ReferenceContext]:
        """Return the current ambient context, or ``None`` if not set."""
        return cls._current.get()

    @classmethod
    def set(cls, value: Optional[ReferenceContext]) -> contextvars.Token:
        """Set the ambient context. Returns a token for restoration.

        Pass the token to :meth:`reset` in a ``finally`` block.
        """
        return cls._current.set(value)

    @classmethod
    def reset(cls, token: contextvars.Token) -> None:
        """Restore the ambient context to its prior value."""
        cls._current.reset(token)
