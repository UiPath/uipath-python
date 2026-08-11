"""Tests for LiveTrackEventDispatcher.

The dispatcher schedules ``provider.track_event_async`` on a private
background asyncio loop so a sync caller never blocks on the
underlying HTTP. Tests focus on:

- ``dispatch`` returns immediately (doesn't block on the coroutine)
- The provider's ``track_event_async`` is awaited with the same kwargs
- Exceptions in the coroutine are swallowed (fire-and-forget contract)
- Multiple concurrent submissions all reach the provider
- ``shutdown`` drains pending coroutines
- Post-shutdown dispatch is silent and does not call the provider
- Saturated in-flight cap drops submissions rather than queueing
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from uipath.platform.governance import UiPathPlatformGovernanceProvider
from uipath.platform.governance._live_track_event_dispatcher import (
    LiveTrackEventDispatcher,
)

_DISPATCHER_MODULE = "uipath.platform.governance._live_track_event_dispatcher"
_DISPATCHER_LOGGER = _DISPATCHER_MODULE


@pytest.fixture
def provider() -> MagicMock:
    """Mock provider — ``track_event_async`` becomes an ``AsyncMock`` via spec."""
    # ``MagicMock(spec=...)`` auto-detects coroutine functions on the spec
    # and creates ``AsyncMock`` attributes for them, so
    # ``provider.track_event_async(...)`` returns an awaitable.
    return MagicMock(spec=UiPathPlatformGovernanceProvider)


@pytest.fixture
def dispatcher(
    provider: MagicMock,
) -> Generator[LiveTrackEventDispatcher, None, None]:
    """Dispatcher with a small in-flight cap for fast tests."""
    d = LiveTrackEventDispatcher(provider, max_inflight=4)
    yield d
    d.shutdown()


def _wait_for(predicate, *, timeout: float = 2.0, interval: float = 0.01) -> bool:
    """Spin-wait helper — returns True when predicate passes, False on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# dispatch is non-blocking
# ---------------------------------------------------------------------------


def test_dispatch_returns_before_provider_completes(
    provider: MagicMock,
    dispatcher: LiveTrackEventDispatcher,
) -> None:
    """dispatch must not wait for the coroutine — the calling thread must not block."""
    started = threading.Event()

    async def _slow_track_event(**_: object) -> None:
        started.set()
        # Sleep long enough that a blocking dispatch would fail the timing bound.
        await asyncio.sleep(0.5)

    provider.track_event_async.side_effect = _slow_track_event

    t0 = time.monotonic()
    dispatcher.dispatch(event_name="agent.started")
    elapsed = time.monotonic() - t0

    # dispatch should return in well under 100ms even though the coroutine
    # is sleeping for 500ms.
    assert elapsed < 0.1, f"dispatch blocked for {elapsed:.3f}s"

    # Coroutine did start (proves the submission landed on the loop).
    assert started.wait(timeout=2.0), "coroutine never started"


# ---------------------------------------------------------------------------
# provider receives the exact kwargs
# ---------------------------------------------------------------------------


def test_dispatch_forwards_kwargs_to_provider(
    provider: MagicMock,
    dispatcher: LiveTrackEventDispatcher,
) -> None:
    """The dispatcher is a thin adapter — every kwarg must reach track_event_async."""
    dispatcher.dispatch(
        event_name="agent.tool_call",
        data={"tool": "browser.open", "url": "https://example.com"},
        operation_id="op-abc-123",
    )

    # Wait for the coroutine to be awaited.
    assert _wait_for(lambda: provider.track_event_async.await_count >= 1), (
        "track_event_async never awaited"
    )

    provider.track_event_async.assert_awaited_once_with(
        event_name="agent.tool_call",
        data={"tool": "browser.open", "url": "https://example.com"},
        operation_id="op-abc-123",
    )


def test_dispatch_passes_none_data_and_operation_id(
    provider: MagicMock,
    dispatcher: LiveTrackEventDispatcher,
) -> None:
    """Defaults — ``data`` and ``operation_id`` flow through as ``None``."""
    dispatcher.dispatch(event_name="agent.idle")

    assert _wait_for(lambda: provider.track_event_async.await_count >= 1)
    provider.track_event_async.assert_awaited_once_with(
        event_name="agent.idle",
        data=None,
        operation_id=None,
    )


# ---------------------------------------------------------------------------
# exceptions are swallowed
# ---------------------------------------------------------------------------


def test_worker_exception_does_not_propagate(
    provider: MagicMock,
    dispatcher: LiveTrackEventDispatcher,
) -> None:
    """Fire-and-forget — dispatch returns before the coroutine runs, so an
    exception raised inside it cannot reach the caller. The dispatcher
    must catch and log internally rather than letting the future
    finalize with an unobserved exception.
    """
    provider.track_event_async.side_effect = RuntimeError("simulated backend 5xx")

    # If the dispatcher leaked the exception, this call would raise.
    dispatcher.dispatch(event_name="agent.deny")

    # And subsequent calls keep working — one bad event doesn't poison
    # the loop.
    provider.track_event_async.side_effect = None
    dispatcher.dispatch(event_name="agent.deny")

    assert _wait_for(lambda: provider.track_event_async.await_count >= 2)
    assert provider.track_event_async.await_count == 2


# ---------------------------------------------------------------------------
# concurrency
# ---------------------------------------------------------------------------


def test_multiple_dispatches_all_reach_provider(provider: MagicMock) -> None:
    """A burst of submissions must all be delivered, in any order."""
    # Use a dedicated dispatcher with headroom well above the burst
    # size so the fast-burst doesn't race the loop into saturation.
    dispatcher = LiveTrackEventDispatcher(provider, max_inflight=64)
    try:
        for i in range(20):
            dispatcher.dispatch(event_name=f"event.{i}")

        assert _wait_for(lambda: provider.track_event_async.await_count == 20)

        seen = {
            call.kwargs["event_name"]
            for call in provider.track_event_async.await_args_list
        }
        assert seen == {f"event.{i}" for i in range(20)}
    finally:
        dispatcher.shutdown()


# ---------------------------------------------------------------------------
# shutdown
# ---------------------------------------------------------------------------


def test_shutdown_waits_for_pending(provider: MagicMock) -> None:
    """``shutdown(wait=True)`` must let in-flight coroutines finish before
    returning so process teardown doesn't lose telemetry.
    """
    completed: list[str] = []

    async def _record(*, event_name: str, **_: object) -> None:
        # Small await so submissions overlap the shutdown call.
        await asyncio.sleep(0.05)
        completed.append(event_name)

    provider.track_event_async.side_effect = _record
    dispatcher = LiveTrackEventDispatcher(provider, max_inflight=10)

    for i in range(5):
        dispatcher.dispatch(event_name=f"event.{i}")

    dispatcher.shutdown(wait=True)

    # Every submission ran to completion by the time shutdown returned.
    assert sorted(completed) == [f"event.{i}" for i in range(5)]


def test_shutdown_is_idempotent(provider: MagicMock) -> None:
    """Calling shutdown twice must not raise — process teardown paths
    sometimes invoke close/shutdown from multiple atexit hooks.
    """
    dispatcher = LiveTrackEventDispatcher(provider, max_inflight=4)
    dispatcher.shutdown()
    dispatcher.shutdown()  # second call: no crash, no exception


# ---------------------------------------------------------------------------
# fire-and-forget safety: dispatch never raises
# ---------------------------------------------------------------------------


def test_dispatch_after_shutdown_is_silent(provider: MagicMock) -> None:
    """After :meth:`shutdown` the dispatcher must silently drop late
    dispatches — a late dispatch (e.g. from an atexit cleanup after
    the loop already stopped) cannot be allowed to raise.
    """
    dispatcher = LiveTrackEventDispatcher(provider, max_inflight=4)
    dispatcher.shutdown(wait=True)

    # If the dispatcher leaked an exception, this call would raise.
    dispatcher.dispatch(event_name="agent.late")

    # And the provider must not have been awaited — the loop is down.
    assert not provider.track_event_async.await_count


def test_shutdown_no_wait_cancels_inflight_cleanly(provider: MagicMock) -> None:
    """``shutdown(wait=False)`` while coroutines are mid-await must cancel
    them and let :meth:`_on_future_done` complete its accounting on the
    cancellation path — no semaphore leak, no leftover future in the
    pending set.

    Regression: ``concurrent.futures.Future.exception()`` *raises*
    ``CancelledError`` when the future was cancelled. If the callback
    doesn't wrap the observation in a targeted ``except``, the discard
    + release calls are skipped → semaphore slots leak (silently,
    because ``Future._invoke_callbacks`` swallows the exception into
    the logger). Without this guard the leak isn't visible at a
    process-level assertion — the loop still stops — so the test must
    check the semaphore state directly.
    """
    n = 3
    release = threading.Event()

    async def _hang_forever(**_: object) -> None:
        # Yield to the loop but never complete — cancelled at teardown.
        while not release.is_set():
            await asyncio.sleep(0.02)

    provider.track_event_async.side_effect = _hang_forever

    dispatcher = LiveTrackEventDispatcher(provider, max_inflight=n)
    try:
        # Fill every in-flight slot so shutdown teardown will cancel
        # every one of them.
        for i in range(n):
            dispatcher.dispatch(event_name=f"event.hang.{i}")
        assert _wait_for(lambda: provider.track_event_async.await_count >= 1)

        # wait=False: don't drain, just stop the loop. The loop's finally
        # block cancels the pending tasks; each cancellation triggers
        # ``_on_future_done`` on the cancelled ``concurrent.futures.Future``.
        dispatcher.shutdown(wait=False)

        # Loop thread joined.
        assert not dispatcher._loop_thread.is_alive(), (
            "loop thread did not stop after shutdown(wait=False)"
        )

        # Accounting cleanly reset — the callback ran to its finally
        # even on the CancelledError path.
        # 1. Pending set drained: every cancelled future was discarded.
        assert not dispatcher._futures, (
            f"cancellation left {len(dispatcher._futures)} future(s) in "
            f"the pending set — semaphore slot(s) leaked"
        )
        # 2. Every in-flight slot released: we can immediately re-acquire
        #    all ``n`` semaphore slots without blocking.
        acquired = 0
        for _ in range(n):
            if dispatcher._inflight.acquire(blocking=False):
                acquired += 1
        for _ in range(acquired):
            dispatcher._inflight.release()
        assert acquired == n, (
            f"expected all {n} semaphore slots free after cancellation, "
            f"only {acquired} were released"
        )
    finally:
        release.set()


def test_dispatch_drops_when_inflight_saturated(provider: MagicMock) -> None:
    """When the in-flight cap is reached, further dispatches are dropped
    rather than queueing unboundedly. The drop must NOT call the
    provider for the saturated submission.
    """
    release = threading.Event()

    async def _blocked(**_: object) -> None:
        # Poll a threading.Event without blocking the loop — a bare
        # ``release.wait()`` would freeze the whole event loop; the
        # small await yields between checks so other coroutines can
        # progress and the semaphore state can be inspected.
        while not release.is_set():
            await asyncio.sleep(0.02)

    provider.track_event_async.side_effect = _blocked

    dispatcher = LiveTrackEventDispatcher(provider, max_inflight=2)
    try:
        # Fill the cap.
        dispatcher.dispatch(event_name="event.1")
        dispatcher.dispatch(event_name="event.2")

        # Wait for at least one coroutine to be awaited (so the
        # semaphore is held by an in-flight task, not just queued).
        assert _wait_for(lambda: provider.track_event_async.await_count >= 1)

        # Third submission should be dropped — semaphore is exhausted.
        dispatcher.dispatch(event_name="event.dropped")

        # event.dropped never reaches the provider.
        assert "event.dropped" not in {
            call.kwargs.get("event_name")
            for call in provider.track_event_async.call_args_list
        }
    finally:
        release.set()
        dispatcher.shutdown(wait=True)


# ---------------------------------------------------------------------------
# construction defaults
# ---------------------------------------------------------------------------


def test_default_max_inflight_matches_module_constant(provider: MagicMock) -> None:
    """Constructor default equals the documented module constant.

    Guards against silent drift between the docstring's cited default
    and the actual value passed to :class:`BoundedSemaphore`.
    """
    dispatcher = LiveTrackEventDispatcher(provider)
    try:
        assert (
            dispatcher._max_inflight == LiveTrackEventDispatcher._DEFAULT_MAX_INFLIGHT
        )
        assert LiveTrackEventDispatcher._DEFAULT_MAX_INFLIGHT == 40
    finally:
        dispatcher.shutdown()


# ---------------------------------------------------------------------------
# uncovered branches: loop-unavailable during dispatch, loop-already-stopped
# during shutdown, and explicit exception-log path
# ---------------------------------------------------------------------------


def test_dispatch_swallows_when_loop_unavailable(
    provider: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Covers the ``RuntimeError`` catch in :meth:`dispatch`.

    Simulates the race where the loop is stopped/closed between the
    shutdown-event check and ``run_coroutine_threadsafe``. dispatch
    must:

    - not raise
    - not call the provider
    - release the semaphore slot it took (so subsequent live dispatches
      can still acquire)
    - log at debug
    """
    dispatcher = LiveTrackEventDispatcher(provider, max_inflight=2)
    try:
        # Force run_coroutine_threadsafe to raise as if the loop were
        # already closed. Patched via the dispatcher module's namespace
        # so the dispatcher sees the fake at its call site.
        def _raise_runtime(*_args: object, **_kwargs: object) -> object:
            raise RuntimeError("Event loop is closed")

        monkeypatch.setattr(
            f"{_DISPATCHER_MODULE}.asyncio.run_coroutine_threadsafe",
            _raise_runtime,
        )

        with caplog.at_level(logging.DEBUG, logger=_DISPATCHER_LOGGER):
            # Fire more calls than max_inflight — if the semaphore is
            # NOT released on the RuntimeError path, we would see a
            # "pool saturated" warning after 2 calls instead of the
            # expected "loop unavailable" debug on every call.
            for i in range(5):
                dispatcher.dispatch(event_name=f"event.oops.{i}")

        # Provider never invoked — the loop is (simulated) dead.
        assert provider.track_event_async.await_count == 0
        assert provider.track_event_async.call_count == 0

        # Debug log fired for each attempt, and no saturation warning.
        debug_hits = [
            r for r in caplog.records if "Telemetry loop unavailable" in r.message
        ]
        saturation_hits = [
            r for r in caplog.records if "Telemetry pool saturated" in r.message
        ]
        assert len(debug_hits) == 5, (
            f"expected 5 loop-unavailable debug logs, got {len(debug_hits)}"
        )
        assert not saturation_hits, (
            "semaphore was not released on RuntimeError — pool saturated after 2 calls"
        )
    finally:
        dispatcher.shutdown()


def test_shutdown_swallows_when_loop_already_stopped(provider: MagicMock) -> None:
    """Covers the ``RuntimeError`` catch in :meth:`shutdown`.

    If the loop is already stopped and closed by the time ``shutdown``
    is called (e.g. the ``_run_loop`` finally block has completed after
    a direct external stop), ``call_soon_threadsafe`` raises. shutdown
    must swallow and complete cleanly.
    """
    dispatcher = LiveTrackEventDispatcher(provider, max_inflight=2)

    # Stop the loop directly, bypassing shutdown(). The ``_run_loop``
    # finally block will run: cancel tasks, gather, then close the
    # loop. When our shutdown() then tries call_soon_threadsafe, the
    # loop is already closed → RuntimeError.
    dispatcher._loop.call_soon_threadsafe(dispatcher._loop.stop)
    dispatcher._loop_thread.join(timeout=5.0)
    assert not dispatcher._loop_thread.is_alive()

    # Must not raise; the internal RuntimeError from the already-closed
    # loop is swallowed.
    dispatcher.shutdown()

    # And is still idempotent afterwards.
    dispatcher.shutdown()


def test_worker_exception_is_logged_at_debug(
    provider: MagicMock,
    dispatcher: LiveTrackEventDispatcher,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Covers the ``except Exception`` branch inside ``_run``.

    Complements :func:`test_worker_exception_does_not_propagate` by
    asserting the log record (with ``exc_info``) actually fires, so
    coverage records the debug-log line inside the coroutine.
    """
    provider.track_event_async.side_effect = ValueError("bad payload")

    with caplog.at_level(logging.DEBUG, logger=_DISPATCHER_LOGGER):
        dispatcher.dispatch(event_name="agent.bad")
        # Wait for the coroutine to run AND the callback to fire so
        # coverage collects the except-branch lines from the loop thread.
        assert _wait_for(lambda: provider.track_event_async.await_count >= 1)
        # Small sleep to let the callback finalize (release semaphore,
        # drop from set) — otherwise coverage may race the callback.
        time.sleep(0.05)

    matching = [
        r
        for r in caplog.records
        if "Failed to dispatch track_event" in r.message and r.levelno == logging.DEBUG
    ]
    assert matching, "expected a debug log for the swallowed exception"
    # exc_info is attached so operators can trace the failure.
    assert matching[0].exc_info is not None
    assert isinstance(matching[0].exc_info[1], ValueError)


# ---------------------------------------------------------------------------
# thread safety
# ---------------------------------------------------------------------------


def test_dispatch_is_safe_from_many_threads(provider: MagicMock) -> None:
    """dispatches from many caller threads all reach the provider.

    Exercises the semaphore, the futures set, and
    ``run_coroutine_threadsafe`` under concurrent access from
    non-loop threads. If the futures-set mutation weren't locked, this
    would race and drop or duplicate futures under load.
    """
    dispatcher = LiveTrackEventDispatcher(provider, max_inflight=128)
    try:
        n_threads = 50
        barrier = threading.Barrier(n_threads)

        def _fire(name: str) -> None:
            # Wait until all threads are ready, then fire together.
            barrier.wait(timeout=2.0)
            dispatcher.dispatch(event_name=name)

        threads = [
            threading.Thread(target=_fire, args=(f"burst.{i}",))
            for i in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert _wait_for(lambda: provider.track_event_async.await_count == n_threads), (
            f"expected {n_threads} awaits, got {provider.track_event_async.await_count}"
        )

        seen = {
            c.kwargs["event_name"] for c in provider.track_event_async.await_args_list
        }
        assert seen == {f"burst.{i}" for i in range(n_threads)}
    finally:
        dispatcher.shutdown()


# ---------------------------------------------------------------------------
# shutdown timeout
# ---------------------------------------------------------------------------


def test_shutdown_respects_timeout_when_drain_stalls(provider: MagicMock) -> None:
    """``shutdown(wait=True, timeout=…)`` must return within the window
    even if pending coroutines are stuck.

    Ensures a stalled backend cannot hang process teardown. Coroutines
    still in flight past the timeout are cancelled by the loop's
    teardown path.
    """
    release = threading.Event()

    async def _never_finish(**_: object) -> None:
        while not release.is_set():
            await asyncio.sleep(0.02)

    provider.track_event_async.side_effect = _never_finish
    dispatcher = LiveTrackEventDispatcher(provider, max_inflight=4)

    dispatcher.dispatch(event_name="stuck.1")
    dispatcher.dispatch(event_name="stuck.2")
    assert _wait_for(lambda: provider.track_event_async.await_count >= 1)

    t0 = time.monotonic()
    try:
        dispatcher.shutdown(wait=True, timeout=0.1)
    finally:
        release.set()
    elapsed = time.monotonic() - t0

    # shutdown(timeout=0.1) waits ≤0.1s on the futures, then stops the
    # loop and joins the thread (5s cap). Total must be well under a
    # few seconds — a hang here would freeze the whole test suite.
    assert elapsed < 3.0, f"shutdown took {elapsed:.3f}s with timeout=0.1s"
    assert not dispatcher._loop_thread.is_alive()
