"""Tests for `get_debug_bridge()` selection matrix.

Locks in the non-breaking-change contract: absence of `attach` preserves the
legacy `job_id`-based selection. Explicit `attach` overrides that selection.
"""

from __future__ import annotations

import pytest

from uipath._cli._debug._bridge import (
    ConsoleDebugBridge,
    SignalRDebugBridge,
    get_debug_bridge,
)
from uipath.runtime import UiPathRuntimeContext
from uipath.runtime.debug import DetachedDebugBridge


def _ctx(**overrides) -> UiPathRuntimeContext:
    return UiPathRuntimeContext(**overrides)


def test_attach_none_returns_detached_bridge_without_job_id():
    bridge = get_debug_bridge(_ctx(), attach="none")
    assert isinstance(bridge, DetachedDebugBridge)


def test_attach_none_returns_detached_bridge_even_when_job_id_set(monkeypatch):
    """'none' wins over job_id — this is the whole point of the flag."""
    monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com")
    bridge = get_debug_bridge(_ctx(job_id="job-123"), attach="none")
    assert isinstance(bridge, DetachedDebugBridge)


def test_attach_signalr_forces_signalr_bridge(monkeypatch):
    monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com")
    bridge = get_debug_bridge(_ctx(job_id="job-123"), attach="signalr")
    assert isinstance(bridge, SignalRDebugBridge)


def test_attach_console_forces_console_bridge_even_when_job_id_set(monkeypatch):
    monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com")
    bridge = get_debug_bridge(_ctx(job_id="job-123"), attach="console")
    assert isinstance(bridge, ConsoleDebugBridge)


def test_legacy_selection_signalr_when_job_id_set_and_no_attach(monkeypatch):
    """Non-breaking change assertion: absence of `attach` preserves today's behavior."""
    monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com")
    bridge = get_debug_bridge(_ctx(job_id="job-123"))
    assert isinstance(bridge, SignalRDebugBridge)


def test_legacy_selection_console_when_no_job_id_and_no_attach():
    """Non-breaking change assertion: absence of `attach` preserves today's behavior."""
    bridge = get_debug_bridge(_ctx())
    assert isinstance(bridge, ConsoleDebugBridge)


def test_attach_signalr_without_job_id_raises():
    """Explicit signalr without job_id is a user error — surface it loudly."""
    with pytest.raises(ValueError, match="UIPATH_URL and UIPATH_JOB_KEY"):
        get_debug_bridge(_ctx(), attach="signalr")
