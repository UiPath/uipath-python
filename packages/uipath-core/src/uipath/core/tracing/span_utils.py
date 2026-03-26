"""Utilities for managing UiPath spans."""

import logging
from typing import Callable, Optional

from opentelemetry import context, trace
from opentelemetry.trace import NonRecordingSpan, Span, set_span_in_context

logger = logging.getLogger(__name__)


class ParentedNonRecordingSpan(NonRecordingSpan):
    """Non-recording span with explicit parent tracking.

    Extends NonRecordingSpan to include a parent attribute, allowing the SpanRegistry
    to properly track parent-child relationships for non-recording spans.
    This is necessary because NonRecordingSpan instances created directly don't have
    their parent automatically set like normal recording spans do.
    """

    def __init__(
        self, context: trace.SpanContext, parent: Optional[trace.SpanContext] = None
    ):
        """Initialize a parented non-recording span.

        Args:
            context: The SpanContext for this span
            parent: Optional parent SpanContext
        """
        super().__init__(context)
        self.parent = parent


class SpanRegistry:
    """Registry to track all spans and their parent relationships."""

    MAX_HIERARCHY_DEPTH = 1000  # Hard limit for hierarchy traversal

    def __init__(self):
        self._spans: dict[int, Span] = {}  # span_id -> span
        self._parent_map: dict[int, Optional[int]] = {}  # span_id -> parent_id

    def register_span(self, span: Span) -> None:
        """Register a span and its parent relationship."""
        span_id = span.get_span_context().span_id

        parent_id: Optional[int] = None

        if hasattr(span, "parent") and span.parent is not None:
            parent_id = getattr(span.parent, "span_id", None)

        self._spans[span_id] = span
        self._parent_map[span_id] = parent_id

        parent_str = "{:016x}".format(parent_id) if parent_id is not None else "None"

        logger.debug(
            "SpanRegistry: registered span: %s (id: %016x, parent: %s)",
            getattr(span, "name", "unknown"),
            span_id,
            parent_str,
        )

    def get_span(self, span_id: int) -> Optional[Span]:
        """Get a span by ID."""
        return self._spans.get(span_id)

    def get_parent_id(self, span_id: int) -> Optional[int]:
        """Get the parent ID of a span."""
        return self._parent_map.get(span_id)

    def calculate_depth(self, span_id: int) -> int:
        """Calculate the depth of a span in the hierarchy.

        Returns:
            The depth of the span, capped at MAX_HIERARCHY_DEPTH.
        """
        depth = 0
        current_id = span_id
        visited = set()

        while current_id is not None and current_id not in visited:
            visited.add(current_id)
            parent_id = self._parent_map.get(current_id)
            if parent_id is None:
                break
            depth += 1
            if depth >= self.MAX_HIERARCHY_DEPTH:
                logger.warning(
                    "Hit MAX_HIERARCHY_DEPTH (%d) while calculating depth for span %016x",
                    self.MAX_HIERARCHY_DEPTH,
                    span_id,
                )
                break
            current_id = parent_id

        return depth

    def is_ancestor(self, ancestor_id: int, descendant_id: int) -> bool:
        """Check if ancestor_id is an ancestor of descendant_id.

        Returns:
            True if ancestor_id is an ancestor of descendant_id, False otherwise.
            If MAX_HIERARCHY_DEPTH is reached, returns False.
        """
        current_id: Optional[int] = descendant_id
        visited = set()
        steps = 0

        while current_id is not None and current_id not in visited:
            if current_id == ancestor_id:
                return True
            visited.add(current_id)
            current_id = self._parent_map.get(current_id)
            steps += 1
            if steps >= self.MAX_HIERARCHY_DEPTH:
                logger.warning(
                    "Hit MAX_HIERARCHY_DEPTH (%d) while checking ancestry between %016x and %016x",
                    self.MAX_HIERARCHY_DEPTH,
                    ancestor_id,
                    descendant_id,
                )
                return False

        return False

    def clear(self) -> None:
        """Clear all registered spans."""
        self._spans.clear()
        self._parent_map.clear()


# Global span registry instance
_span_registry = SpanRegistry()


class UiPathSpanUtils:
    """Static utility class to manage tracing implementations and decorated functions."""

    _current_span_provider: Optional[Callable[[], Optional[Span]]] = None
    _current_span_ancestors_provider: Optional[Callable[[], list[Span]]] = None

    @staticmethod
    def register_current_span_provider(
        current_span_provider: Optional[Callable[[], Optional[Span]]],
    ):
        """Register a custom current span provider function.

        Args:
            current_span_provider: A function that returns the current span from an external
                                 tracing framework. If None, no custom span parenting will be used.
        """
        UiPathSpanUtils._current_span_provider = current_span_provider

    @staticmethod
    def get_parent_context() -> context.Context:
        """Get the parent context for span creation.

        This method determines the correct parent context when creating a new traced span.
        It handles scenarios where spans may exist in both OpenTelemetry's context (current_span)
        and in an external tracing system (external_span), such as LangGraph.

        The algorithm follows this priority:

        1. **No spans available**: Returns the current OpenTelemetry context (empty context)

        2. **Only current_span exists**: Returns a context with current_span set as parent
           - This is the standard OpenTelemetry behavior for nested traced functions

        3. **Only external_span exists**: Returns a context with external_span set as parent
           - This occurs when an external tracing system (like LangGraph) has an active span
             but there's no OTel span in the current call stack

        4. **Both spans exist**: Calls `_get_bottom_most_span()` to determine which is deeper
           - Uses the SpanRegistry to build parent-child relationships
           - Returns the span that is closer to the "bottom" (leaf) of the trace tree
           - This ensures new spans are always attached to the deepest/most specific parent

        Context Sources:
        - **current_span**: Retrieved from OpenTelemetry's `trace.get_current_span()`
          - Represents the active OTel span in the current execution context
          - Created by `@traced` decorators or manual span creation

        - **external_span**: Retrieved from the registered custom span provider
          - Set via `register_current_span_provider()`
          - Typically provided by external frameworks (LangGraph, LangChain, etc.)
          - Allows integration with tracing systems outside of OpenTelemetry

        Returns:
            context.Context: An OpenTelemetry context containing the appropriate parent span,
                           or the current empty context if no spans are available

        Example:
            ```python
            # Called by the @traced decorator when creating a new span:
            ctx = UiPathTracingManager.get_parent_context()
            with tracer.start_as_current_span("my_span", context=ctx) as span:
                # New span will have the correct parent based on the logic above
                pass
            ```

        See Also:
            - `_get_bottom_most_span()`: Logic for choosing between two available spans
            - `register_current_span_provider()`: Register external span provider
            - `get_external_current_span()`: Retrieve span from external provider
        """
        current_span = trace.get_current_span()
        has_current_span = (
            current_span is not None and current_span.get_span_context().is_valid
        )

        external_span = UiPathSpanUtils.get_external_current_span()

        # Only one or no spans available
        if not has_current_span:
            return (
                set_span_in_context(external_span)
                if external_span is not None
                else context.get_current()
            )
        if external_span is None:
            return set_span_in_context(current_span)

        # Both spans exist - find the bottom-most one
        bottom_span = UiPathSpanUtils._get_bottom_most_span(current_span, external_span)
        return set_span_in_context(bottom_span)

    @staticmethod
    def _get_bottom_most_span(
        current_span: Span,
        external_span: Span,
    ) -> Span:
        """Determine which span is deeper in the ancestor tree.

        Args:
            current_span: The OTel current span
            external_span: The external span from the provider

        Returns:
            The span that is deeper (closer to the bottom) in the call hierarchy
        """
        # Register both spans in the registry
        _span_registry.register_span(current_span)
        _span_registry.register_span(external_span)

        # Also register external ancestors
        external_ancestors = UiPathSpanUtils.get_ancestor_spans() or []
        for ancestor in external_ancestors:
            _span_registry.register_span(ancestor)

        current_span_id = current_span.get_span_context().span_id
        external_span_id = external_span.get_span_context().span_id

        # Check if one span is an ancestor of the other
        if _span_registry.is_ancestor(external_span_id, current_span_id):
            logger.debug(
                "Traced Context: current_span is a descendant of external_span -> returning current_span (deeper)"
            )
            return current_span
        elif _span_registry.is_ancestor(current_span_id, external_span_id):
            logger.debug(
                "Traced Context: external_span is a descendant of current_span -> returning external_span (deeper)"
            )
            return external_span

        # Neither is an ancestor of the other - they're in different branches
        # Use depth as tiebreaker
        current_depth = _span_registry.calculate_depth(current_span_id)
        external_depth = _span_registry.calculate_depth(external_span_id)

        if current_depth > external_depth:
            logger.debug(
                "Traced Context: Different branches, current_span is deeper (depth %d > %d) -> returning current_span",
                current_depth,
                external_depth,
            )
            return current_span
        elif external_depth > current_depth:
            logger.debug(
                "Traced Context: Different branches, external_span is deeper (depth %d > %d) -> returning external_span",
                external_depth,
                current_depth,
            )
            return external_span
        else:
            # Same depth, different branches - default to external
            logger.debug(
                "Traced Context: Same depth (%d), different branches -> defaulting to external_span",
                current_depth,
            )
            return external_span

    @staticmethod
    def get_external_current_span() -> Optional[Span]:
        """Get the current span from the external provider, if any."""
        if UiPathSpanUtils._current_span_provider is not None:
            try:
                return UiPathSpanUtils._current_span_provider()
            except Exception as e:
                logger.warning("Error getting current span from provider: %s", e)
        return None

    @staticmethod
    def get_ancestor_spans() -> list[Span]:
        """Get the ancestor spans from the registered provider, if any."""
        if UiPathSpanUtils._current_span_ancestors_provider is not None:
            try:
                return UiPathSpanUtils._current_span_ancestors_provider()
            except Exception as e:
                logger.warning("Error getting ancestor spans from provider: %s", e)
        return []

    @staticmethod
    def register_current_span_ancestors_provider(
        current_span_ancestors_provider: Optional[Callable[[], list[Span]]],
    ):
        """Register a custom current span ancestors provider function.

        Args:
            current_span_ancestors_provider: A function that returns a list of ancestor spans
                                           from an external tracing framework. If None, no custom
                                           span ancestor information will be used.
        """
        UiPathSpanUtils._current_span_ancestors_provider = (
            current_span_ancestors_provider
        )

    @staticmethod
    def get_current_span_ancestors_provider():
        """Get the currently set custom span ancestors provider."""
        return UiPathSpanUtils._current_span_ancestors_provider


__all__ = ["ParentedNonRecordingSpan", "UiPathSpanUtils"]
