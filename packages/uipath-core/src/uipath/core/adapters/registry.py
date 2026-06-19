"""Ordered registry of framework adapters.

The registry is a pure, implementation-agnostic container — it does
**not** know about any concrete adapter. Plugin packages (e.g.
``uipath-langchain``) populate it by either:

1. Declaring a ``uipath.governance.adapters`` entry point whose value
   is a zero-arg callable that calls :meth:`AdapterRegistry.register`.
   These are auto-discovered on first call to
   :func:`get_adapter_registry`.
2. Calling :meth:`AdapterRegistry.register` directly at import time
   (e.g. side-effect on importing the plugin's governance submodule).

Adapters are checked in priority order (highest first): more specific
adapters get a higher :attr:`BaseAdapter.priority` so they win
``can_handle`` resolution over generic ones, regardless of the order in
which plugin packages happen to be imported. Among adapters with the
same priority, registration order is preserved. Adapters with
``is_fallback=True`` sort last when registered without an explicit
``position`` — passing ``position`` to :meth:`AdapterRegistry.register`
is an escape hatch that bypasses both priority and fallback ordering,
so callers using it own the resulting list order.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseAdapter

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "uipath.governance.adapters"


class AdapterRegistry:
    """Ordered list of adapters; resolves the first match for an agent."""

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._adapters: list[BaseAdapter] = []

    def register(self, adapter: BaseAdapter, position: int | None = None) -> None:
        """Register an adapter.

        Args:
            adapter: The adapter to register.
            position: Explicit insertion index (``0`` = highest priority)
                that bypasses both priority-based ordering AND fallback
                semantics — the adapter is inserted blindly at the given
                index, so callers using ``position`` are responsible for
                not placing a fallback before a specific adapter (or a
                specific adapter after an existing fallback). When
                ``None`` the adapter is inserted by
                :attr:`BaseAdapter.priority` (higher first, stable on
                ties) and before any adapter marked
                :attr:`BaseAdapter.is_fallback`; adapters whose own
                ``is_fallback`` is set are appended last.
        """
        if position is not None:
            self._adapters.insert(position, adapter)
        elif adapter.is_fallback:
            self._adapters.append(adapter)
        else:
            insert_at = len(self._adapters)
            for i, existing in enumerate(self._adapters):
                if existing.is_fallback or existing.priority < adapter.priority:
                    insert_at = i
                    break
            self._adapters.insert(insert_at, adapter)
        logger.debug("Registered adapter: %s", adapter.name)

    def resolve(self, agent: Any) -> BaseAdapter | None:
        """Return the first adapter that can handle ``agent`` (or ``None``)."""
        for adapter in self._adapters:
            try:
                if adapter.can_handle(agent):
                    logger.debug(
                        "AdapterRegistry: %s -> %s",
                        type(agent).__name__,
                        adapter.name,
                    )
                    return adapter
            except Exception as exc:
                logger.warning(
                    "Adapter %s.can_handle() failed: %s",
                    adapter.name,
                    exc,
                )
                continue
        return None

    def get_all(self) -> list[BaseAdapter]:
        """Return a copy of the registered adapters in priority order."""
        return self._adapters.copy()

    def clear(self) -> None:
        """Remove all registered adapters."""
        self._adapters.clear()


_registry: AdapterRegistry | None = None


def _discover_entry_point_adapters() -> None:
    """Load every adapter advertised under the ``uipath.governance.adapters`` group.

    Each entry-point value must be a zero-arg callable (typically a
    ``register_*`` function in the plugin package) that calls
    :meth:`AdapterRegistry.register`. A failure to load or invoke any
    one entry point is logged and skipped — a single broken plugin
    must never block governance startup.
    """
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover - importlib.metadata is stdlib in py3.11+
        return

    try:
        eps = entry_points(group=ENTRY_POINT_GROUP)
    except Exception as exc:  # noqa: BLE001 - discovery failures must never raise
        logger.debug("Adapter entry-point discovery failed: %s", exc, exc_info=True)
        return

    for ep in eps:
        try:
            registrar = ep.load()
        except Exception as exc:  # noqa: BLE001 - one broken plugin must not block others
            logger.debug(
                "Failed to load governance adapter entry point '%s' (%s): %s",
                ep.name,
                ep.value,
                exc,
                exc_info=True,
            )
            continue
        if not callable(registrar):
            logger.warning(
                "Governance adapter entry point '%s' is not callable: %r",
                ep.name,
                registrar,
            )
            continue
        try:
            registrar()
        except Exception as exc:  # noqa: BLE001 - one broken plugin must not block others
            logger.debug(
                "Governance adapter '%s' register call failed: %s",
                ep.name,
                exc,
                exc_info=True,
            )


def get_adapter_registry() -> AdapterRegistry:
    """Return the process-wide adapter registry singleton.

    On first call, discovers and registers every adapter declared under
    the ``uipath.governance.adapters`` entry-point group, so framework
    SDKs (``uipath-langchain``, ``uipath-openai``, …) just need to be
    installed — no explicit import is required.
    """
    global _registry
    if _registry is None:
        _registry = AdapterRegistry()
        _discover_entry_point_adapters()
    return _registry


def reset_adapter_registry() -> None:
    """Drop the singleton registry (intended for tests)."""
    global _registry
    if _registry is not None:
        _registry.clear()
    _registry = None
