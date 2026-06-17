"""Tests for AdapterRegistry — ordering, resolution, entry-point discovery."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from uipath.core.adapters import BaseAdapter, EvaluatorProtocol
from uipath.core.adapters.registry import (
    AdapterRegistry,
    _discover_entry_point_adapters,
    get_adapter_registry,
    reset_adapter_registry,
)

# ---------------------------------------------------------------------------
# Test adapters
# ---------------------------------------------------------------------------


class _SpecificAdapter(BaseAdapter):
    """Matches only objects with a ``__specific__`` marker."""

    @property
    def name(self) -> str:
        return "specific"

    def can_handle(self, agent: Any) -> bool:
        return hasattr(agent, "__specific__")

    def attach(
        self,
        agent: Any,
        agent_id: str,
        session_id: str,
        evaluator: EvaluatorProtocol,
    ) -> Any:
        return agent


class _FallbackAdapter(BaseAdapter):
    """Matches anything — must always sort last."""

    is_fallback = True

    @property
    def name(self) -> str:
        return "fallback"

    def can_handle(self, agent: Any) -> bool:
        return True

    def attach(
        self,
        agent: Any,
        agent_id: str,
        session_id: str,
        evaluator: EvaluatorProtocol,
    ) -> Any:
        return agent


class _SecondaryAdapter(BaseAdapter):
    """Another specific adapter, used to test ordering between two specifics."""

    @property
    def name(self) -> str:
        return "secondary"

    def can_handle(self, agent: Any) -> bool:
        return hasattr(agent, "__secondary__")

    def attach(
        self,
        agent: Any,
        agent_id: str,
        session_id: str,
        evaluator: EvaluatorProtocol,
    ) -> Any:
        return agent


class _HighPriorityAdapter(BaseAdapter):
    """Specific adapter with an elevated priority."""

    priority = 100

    @property
    def name(self) -> str:
        return "high"

    def can_handle(self, agent: Any) -> bool:
        return True

    def attach(
        self,
        agent: Any,
        agent_id: str,
        session_id: str,
        evaluator: EvaluatorProtocol,
    ) -> Any:
        return agent


class _LowPriorityAdapter(BaseAdapter):
    """Generic adapter that should yield to higher-priority specifics."""

    priority = -10

    @property
    def name(self) -> str:
        return "low"

    def can_handle(self, agent: Any) -> bool:
        return True

    def attach(
        self,
        agent: Any,
        agent_id: str,
        session_id: str,
        evaluator: EvaluatorProtocol,
    ) -> Any:
        return agent


class _BrokenAdapter(BaseAdapter):
    """``can_handle`` raises — must be skipped, not crash resolution."""

    @property
    def name(self) -> str:
        return "broken"

    def can_handle(self, agent: Any) -> bool:
        raise RuntimeError("can_handle exploded")

    def attach(
        self,
        agent: Any,
        agent_id: str,
        session_id: str,
        evaluator: EvaluatorProtocol,
    ) -> Any:
        raise RuntimeError("attach exploded")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_global_registry():
    """Each test starts with no singleton registry."""
    reset_adapter_registry()
    yield
    reset_adapter_registry()


# ---------------------------------------------------------------------------
# register / resolve / get_all / clear
# ---------------------------------------------------------------------------


def test_empty_registry_resolves_to_none():
    reg = AdapterRegistry()
    assert reg.resolve(object()) is None
    assert reg.get_all() == []


def test_register_appends_in_order():
    reg = AdapterRegistry()
    a, b = _SpecificAdapter(), _SecondaryAdapter()
    reg.register(a)
    reg.register(b)
    assert reg.get_all() == [a, b]


def test_resolve_returns_first_matching_adapter():
    reg = AdapterRegistry()
    reg.register(_SpecificAdapter())
    reg.register(_SecondaryAdapter())

    agent = MagicMock()
    agent.__secondary__ = True  # only secondary should match
    resolved = reg.resolve(agent)
    assert resolved is not None
    assert resolved.name == "secondary"


def test_resolve_skips_broken_can_handle_and_continues():
    """A can_handle() that raises must not break the whole resolve loop."""
    reg = AdapterRegistry()
    reg.register(_BrokenAdapter())
    reg.register(_SpecificAdapter())

    agent = MagicMock()
    agent.__specific__ = True
    resolved = reg.resolve(agent)
    assert resolved is not None
    assert resolved.name == "specific"


def test_register_position_inserts_at_index():
    reg = AdapterRegistry()
    a, b, c = _SpecificAdapter(), _SecondaryAdapter(), _SpecificAdapter()
    reg.register(a)
    reg.register(b)
    reg.register(c, position=0)  # c jumps to head
    assert reg.get_all()[0] is c
    assert reg.get_all()[1:] == [a, b]


def test_higher_priority_adapter_inserted_before_lower_priority():
    """A specific (higher-priority) adapter must sort before a generic one
    even when the generic one was registered first."""
    reg = AdapterRegistry()
    generic = _LowPriorityAdapter()
    specific = _HighPriorityAdapter()
    reg.register(generic)
    reg.register(specific)  # registered later, but higher priority

    adapters = reg.get_all()
    assert adapters[0] is specific
    assert adapters[1] is generic


def test_same_priority_preserves_registration_order():
    """Adapters with equal priority should fall back to insertion order."""
    reg = AdapterRegistry()
    a, b = _SpecificAdapter(), _SecondaryAdapter()  # both priority=0
    reg.register(a)
    reg.register(b)
    assert reg.get_all() == [a, b]


def test_higher_priority_adapter_inserted_before_fallback():
    """High-priority adapter goes in front of an already-registered fallback."""
    reg = AdapterRegistry()
    fallback = _FallbackAdapter()
    reg.register(fallback)
    reg.register(_HighPriorityAdapter())

    adapters = reg.get_all()
    assert adapters[0].name == "high"
    assert adapters[-1] is fallback


def test_lower_priority_adapter_inserted_before_fallback_after_specifics():
    """Negative-priority adapter sorts after default-priority specifics but
    still before the fallback."""
    reg = AdapterRegistry()
    reg.register(_SpecificAdapter())  # priority=0
    reg.register(_FallbackAdapter())
    reg.register(_LowPriorityAdapter())  # priority=-10

    adapters = reg.get_all()
    assert adapters[0].name == "specific"
    assert adapters[1].name == "low"
    assert adapters[-1].name == "fallback"


def test_priority_overrides_registration_order_in_resolve():
    """Resolution must follow priority ordering, not registration order."""
    reg = AdapterRegistry()
    reg.register(_LowPriorityAdapter())  # both adapters match every agent,
    reg.register(_HighPriorityAdapter())  # so priority decides which wins.

    resolved = reg.resolve(object())
    assert resolved is not None
    assert resolved.name == "high"


def test_fallback_stays_last_when_new_adapter_registered():
    """When the last entry has ``is_fallback`` set, new adapters insert before it."""
    reg = AdapterRegistry()
    fallback = _FallbackAdapter()
    reg.register(fallback)
    reg.register(_SpecificAdapter())  # this should insert BEFORE fallback

    adapters = reg.get_all()
    assert adapters[-1] is fallback
    assert adapters[0].name == "specific"


def test_fallback_resolves_only_when_no_specific_matches():
    reg = AdapterRegistry()
    reg.register(_SpecificAdapter())
    reg.register(_FallbackAdapter())

    # Agent without the __specific__ marker → fallback wins.
    resolved = reg.resolve(object())
    assert resolved is not None
    assert resolved.name == "fallback"


def test_clear_removes_all_adapters():
    reg = AdapterRegistry()
    reg.register(_SpecificAdapter())
    reg.register(_SecondaryAdapter())
    reg.clear()
    assert reg.get_all() == []
    assert reg.resolve(object()) is None


def test_get_all_returns_copy_not_internal_list():
    """Callers must not be able to mutate the registry through get_all()."""
    reg = AdapterRegistry()
    reg.register(_SpecificAdapter())
    snapshot = reg.get_all()
    snapshot.clear()
    assert len(reg.get_all()) == 1  # unaffected


# ---------------------------------------------------------------------------
# Singleton + entry-point discovery
# ---------------------------------------------------------------------------


def test_get_adapter_registry_returns_singleton():
    reg1 = get_adapter_registry()
    reg2 = get_adapter_registry()
    assert reg1 is reg2


def test_reset_adapter_registry_drops_singleton():
    first = get_adapter_registry()
    reset_adapter_registry()
    second = get_adapter_registry()
    assert first is not second


def test_entry_point_discovery_invokes_registrars(monkeypatch):
    """Each entry-point's zero-arg callable must be loaded and called."""
    called: list[str] = []

    def make_registrar(name: str):
        def _register() -> None:
            called.append(name)

        return _register

    ep_a = MagicMock()
    ep_a.name = "a"
    ep_a.value = "pkg_a:register"
    ep_a.load.return_value = make_registrar("a")

    ep_b = MagicMock()
    ep_b.name = "b"
    ep_b.value = "pkg_b:register"
    ep_b.load.return_value = make_registrar("b")

    monkeypatch.setattr(
        "uipath.core.adapters.registry.entry_points",
        lambda group: [ep_a, ep_b] if group == "uipath.governance.adapters" else [],
        raising=False,
    )

    # entry_points lives in importlib.metadata; the registry imports it
    # lazily inside the function. Patch the import target directly.
    import importlib.metadata as importlib_metadata

    monkeypatch.setattr(
        importlib_metadata,
        "entry_points",
        lambda group=None: (
            [ep_a, ep_b] if group == "uipath.governance.adapters" else []
        ),
    )

    _discover_entry_point_adapters()
    assert sorted(called) == ["a", "b"]


def test_entry_point_discovery_skips_broken_loader(monkeypatch):
    """One broken entry-point must not stop the others from registering."""
    called: list[str] = []

    ep_broken = MagicMock()
    ep_broken.name = "broken"
    ep_broken.value = "pkg_broken:register"
    ep_broken.load.side_effect = ImportError("cannot import")

    ep_ok = MagicMock()
    ep_ok.name = "ok"
    ep_ok.value = "pkg_ok:register"
    ep_ok.load.return_value = lambda: called.append("ok")

    import importlib.metadata as importlib_metadata

    monkeypatch.setattr(
        importlib_metadata,
        "entry_points",
        lambda group=None: (
            [ep_broken, ep_ok] if group == "uipath.governance.adapters" else []
        ),
    )

    _discover_entry_point_adapters()  # must not raise
    assert called == ["ok"]


def test_entry_point_discovery_skips_non_callable(monkeypatch):
    """An entry-point that resolves to a non-callable must be logged and skipped."""
    called: list[str] = []

    ep_bad = MagicMock()
    ep_bad.name = "bad"
    ep_bad.value = "pkg_bad:NOT_A_FUNCTION"
    ep_bad.load.return_value = "not callable"

    ep_ok = MagicMock()
    ep_ok.name = "ok"
    ep_ok.value = "pkg_ok:register"
    ep_ok.load.return_value = lambda: called.append("ok")

    import importlib.metadata as importlib_metadata

    monkeypatch.setattr(
        importlib_metadata,
        "entry_points",
        lambda group=None: (
            [ep_bad, ep_ok] if group == "uipath.governance.adapters" else []
        ),
    )

    _discover_entry_point_adapters()
    assert called == ["ok"]


def test_entry_point_discovery_swallows_registrar_exception(monkeypatch):
    """A registrar that raises mid-call must not stop subsequent registrars."""
    called: list[str] = []

    def _raises() -> None:
        raise RuntimeError("registrar exploded")

    ep_raising = MagicMock()
    ep_raising.name = "raises"
    ep_raising.value = "pkg:register"
    ep_raising.load.return_value = _raises

    ep_ok = MagicMock()
    ep_ok.name = "ok"
    ep_ok.value = "pkg:register2"
    ep_ok.load.return_value = lambda: called.append("ok")

    import importlib.metadata as importlib_metadata

    monkeypatch.setattr(
        importlib_metadata,
        "entry_points",
        lambda group=None: (
            [ep_raising, ep_ok] if group == "uipath.governance.adapters" else []
        ),
    )

    _discover_entry_point_adapters()
    assert called == ["ok"]


def test_entry_point_discovery_swallows_entry_points_failure(monkeypatch):
    """If ``entry_points()`` itself raises, discovery must log and return cleanly."""
    import importlib.metadata as importlib_metadata

    def _boom(group=None):
        raise RuntimeError("entry_points API exploded")

    monkeypatch.setattr(importlib_metadata, "entry_points", _boom)

    # Must not raise — and must not register anything.
    _discover_entry_point_adapters()
    reg = get_adapter_registry()
    assert reg.get_all() == []


# ---------------------------------------------------------------------------
# Protocol conformance smoke tests
# ---------------------------------------------------------------------------


def test_baseadapter_is_abc():
    """BaseAdapter must be abstract — direct instantiation must fail."""
    with pytest.raises(TypeError):
        BaseAdapter()  # type: ignore[abstract]


def test_concrete_adapter_is_baseadapter():
    """A concrete subclass must be recognized as a BaseAdapter."""
    assert isinstance(_SpecificAdapter(), BaseAdapter)
