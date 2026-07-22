"""Non-blocking dispatcher for governance track-event telemetry.

Wraps :meth:`UiPathPlatformGovernanceProvider.track_event_async` on a
private background ``asyncio`` event loop so sync callers can fire
telemetry events without blocking on the underlying ``POST /runtime/log``
HTTP round-trip.

:meth:`LiveTrackEventDispatcher.dispatch` is a sync fire-and-forget
method that mirrors the kwargs of ``track_event_async``. Internally it
schedules the async HTTP call onto a dedicated background loop, so the
calling thread never blocks on network I/O and the underlying HTTP call
remains async end-to-end.

Design notes:

- **Async HTTP inside, sync interface outside.** ``dispatch`` is a
  sync function. Internally it enqueues a coroutine that awaits
  ``provider.track_event_async``.

- **Loop affinity.** ``httpx.AsyncClient`` lazy-binds its connection
  pool to the first event loop that awaits on it. This dispatcher
  assumes it owns the provider's async HTTP path — nothing else in
  the process should await ``track_event_async`` (or any other
  ``*_async`` method on the same underlying service) on a *different*
  loop. In particular, the provider passed in must be backed by a
  service whose async client has not already served a request on
  another loop (e.g. a governance policy fetch on the CLI's main
  loop) — hand the dispatcher a *dedicated* provider. See "one
  dispatcher per provider" below.

- **Backpressure.** A ``BoundedSemaphore`` caps in-flight coroutines;
  submissions that exceed the cap are dropped with a warning so
  memory stays bounded when the backend is slow.

- **Fire-and-forget contract.** Coroutine exceptions are observed on
  the returned ``concurrent.futures.Future`` (to suppress asyncio's
  "exception was never retrieved" warning) and logged at debug — they
  cannot reach the caller because ``dispatch`` returns before the
  coroutine runs.

One dispatcher per provider. The dispatcher's background loop must be
the only loop that awaits the provider's async methods.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
from typing import Any

from ._governance_provider import UiPathPlatformGovernanceProvider

logger = logging.getLogger(__name__)


class LiveTrackEventDispatcher:
    """Non-blocking sync adapter around ``provider.track_event_async``.

    Schedules governance telemetry events on a private background
    ``asyncio`` loop so the calling thread is never blocked on the
    platform's ``/runtime/log`` HTTP call — and the HTTP call itself
    is awaited (not run on a sync thread pool).

    .. code-block:: python

        provider = UiPathPlatformGovernanceProvider(config=..., execution_context=...)
        dispatcher = LiveTrackEventDispatcher(provider)
        dispatcher.dispatch(event_name="agent.started")
        # ...
        dispatcher.shutdown()  # at process exit

    ``dispatch`` has the same kwargs as
    :meth:`UiPathPlatformGovernanceProvider.track_event_async` so it is
    a drop-in sync callable for anywhere the async method would go.
    """

    _DEFAULT_MAX_INFLIGHT = 40

    # Total wall-clock ceiling for a single dispatched call. The platform
    # call retries (up to 5 attempts, honoring ``Retry-After`` up to 120s)
    # and httpx's 30s timeout is per-phase, not total — so one degraded
    # call could otherwise run for minutes, pinning an in-flight slot and
    # stalling ``shutdown`` drain. This caps every dispatched call.
    _PER_CALL_DEADLINE_SECONDS = 60.0

    # Max wait for the background loop thread to signal readiness. The
    # thread only fails to signal if it never starts (e.g. OS
    # thread-creation failure); the caller treats a construction failure as
    # "governance unavailable" (fail open) rather than blocking forever.
    _LOOP_START_TIMEOUT_SECONDS = 5.0

    def __init__(
        self,
        provider: UiPathPlatformGovernanceProvider,
        *,
        max_inflight: int = _DEFAULT_MAX_INFLIGHT,
    ) -> None:
        """Construct a dispatcher bound to one provider.

        Starts a daemon thread that runs a private ``asyncio`` event
        loop. All HTTP awaits happen on that loop; nothing else in the
        process should await the provider's async methods on a
        different loop (see the module docstring on loop affinity).

        Args:
            provider: The platform governance provider whose
                ``track_event_async`` will be awaited on the background
                loop.
            max_inflight: Cap on concurrent in-flight coroutines. When
                exceeded, further ``dispatch`` calls are dropped with a
                warning so memory stays bounded under a slow backend.
                Default 40 is sized for a bursty-but-not-sustained
                event stream.
        """
        self._provider = provider
        self._max_inflight = max_inflight
        self._inflight = threading.BoundedSemaphore(max_inflight)
        self._shutdown_event = threading.Event()
        self._futures_lock = threading.Lock()
        self._futures: set[concurrent.futures.Future[None]] = set()
        # Guards warn-once for swallowed dispatch failures. Only ever read
        # or written on the background loop thread (inside ``_run``), so no
        # lock is needed.
        self._dispatch_failure_logged = False

        self._loop = asyncio.new_event_loop()
        self._loop_ready = threading.Event()
        self._loop_thread = threading.Thread(
            target=self._run_loop,
            name="governance-track-event-loop",
            daemon=True,
        )
        self._loop_thread.start()
        # Block until the loop is running so the first ``dispatch`` cannot
        # race with startup and hit "loop not running" errors. Bounded so a
        # thread that never starts surfaces as a construction failure the
        # caller can fall back on, instead of hanging the process forever.
        if not self._loop_ready.wait(timeout=self._LOOP_START_TIMEOUT_SECONDS):
            # Signal the (possibly late-starting) loop thread to abort and
            # close its own loop. NEVER close it here, across threads — that
            # would race the thread's ``run_forever`` (closing a running
            # loop, or running an already-closed one). See ``_run_loop``.
            self._shutdown_event.set()
            raise RuntimeError(
                "governance track-event loop failed to start within "
                f"{self._LOOP_START_TIMEOUT_SECONDS}s"
            )

    def _run_loop(self) -> None:
        """Body of the background loop thread — runs until ``shutdown``."""
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
        # If construction already gave up waiting for readiness (the
        # loop-start-timeout path set ``_shutdown_event`` before this thread
        # got scheduled), abort now and close the loop HERE — on the thread
        # that owns it — so ``__init__`` never closes it across threads.
        if self._shutdown_event.is_set():
            self._loop.close()
            return
        try:
            self._loop.run_forever()
        finally:
            # After ``run_forever`` returns (from ``stop()``), any tasks
            # that were still awaiting mid-flight need to be cancelled
            # and finalized before the loop can close cleanly. Without
            # this, ``loop.close()`` warns "Task was destroyed but it is
            # pending" for every unfinished awaiter.
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception as exc:  # noqa: BLE001 - teardown must not raise
                logger.debug("Loop cleanup swallowed exception: %s", exc)
            finally:
                try:
                    self._loop.close()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Loop close swallowed exception: %s", exc)

    def dispatch(
        self,
        *,
        event_name: str,
        data: dict[str, Any] | None = None,
        operation_id: str | None = None,
    ) -> None:
        """Schedule a track-event call on the background loop — returns immediately.

        The kwargs mirror
        :meth:`UiPathPlatformGovernanceProvider.track_event_async` so
        this method is a drop-in sync callable for the async provider
        method.

        Failure modes — all silent, never raised to the caller:

        - **Post-shutdown**: dispatch after :meth:`shutdown` returns
          silently; the provider is not called.
        - **Saturated in-flight cap**: when ``max_inflight`` coroutines
          are already scheduled, the call is dropped with a warning.
          Telemetry must never grow memory without bound when the
          backend is slow.
        - **Loop unavailable**: ``asyncio.run_coroutine_threadsafe``
          raises ``RuntimeError`` if the loop is stopped/closed
          (late-firing atexit path); the dispatcher rolls back the
          semaphore slot, closes the coroutine, and logs at debug.
        - **Coroutine exception / deadline**: the provider's HTTP call may
          raise for any reason (serialization, 5xx, transport) or exceed
          ``_PER_CALL_DEADLINE_SECONDS``. ``_run`` catches both, logs the
          first such failure at warning (so silent telemetry loss is
          visible) and the rest at debug, and the done-callback observes
          the future to suppress asyncio's "exception was never retrieved"
          warning.
        """
        if self._shutdown_event.is_set():
            logger.debug(
                "Dispatcher shut down; dropping track_event (event_name=%s)",
                event_name,
            )
            return

        if not self._inflight.acquire(blocking=False):
            logger.warning(
                "Telemetry pool saturated (>%d in flight); dropping track_event "
                "(event_name=%s)",
                self._max_inflight,
                event_name,
            )
            return

        coro = self._run(event_name=event_name, data=data, operation_id=operation_id)
        try:
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        except RuntimeError as exc:
            # Loop is stopped/closed — release the slot we took and
            # close the coroutine so it doesn't warn at GC time.
            coro.close()
            self._inflight.release()
            logger.debug(
                "Telemetry loop unavailable (event_name=%s): %s",
                event_name,
                exc,
            )
            return

        with self._futures_lock:
            self._futures.add(future)
        future.add_done_callback(self._on_future_done)

    async def _run(
        self,
        *,
        event_name: str,
        data: dict[str, Any] | None,
        operation_id: str | None,
    ) -> None:
        """Coroutine body — the async HTTP call itself, under a total deadline."""
        try:
            async with asyncio.timeout(self._PER_CALL_DEADLINE_SECONDS) as cm:
                await self._provider.track_event_async(
                    event_name=event_name,
                    data=data,
                    operation_id=operation_id,
                )
        except TimeoutError as exc:
            # ``cm.expired()`` disambiguates OUR deadline from a TimeoutError
            # raised inside the provider call itself (e.g. a socket timeout —
            # ``socket.timeout`` is aliased to ``TimeoutError``). Only the
            # former is a deadline drop; the latter is a normal failure and
            # deserves the exc_info-carrying generic log.
            if cm.expired():
                # The platform call outran the per-call deadline (retries +
                # Retry-After can otherwise run for minutes). Drop it rather
                # than let a degraded backend pin an in-flight slot.
                self._log_dispatch_failure(
                    "track_event exceeded the %.0fs deadline; dropped (event_name=%s)",
                    self._PER_CALL_DEADLINE_SECONDS,
                    event_name,
                )
            else:
                self._log_dispatch_failure(
                    "Failed to dispatch track_event (event_name=%s): %s",
                    event_name,
                    exc,
                    exc_info=True,
                )
        except Exception as exc:  # noqa: BLE001 - fire-and-forget contract
            self._log_dispatch_failure(
                "Failed to dispatch track_event (event_name=%s): %s",
                event_name,
                exc,
                exc_info=True,
            )

    def _log_dispatch_failure(
        self, msg: str, *args: object, exc_info: bool = False
    ) -> None:
        """Log a swallowed dispatch failure — first at warning, then debug.

        Dispatch failures are silent to the caller by the fire-and-forget
        contract, so the first one is surfaced at warning to make telemetry
        loss visible; subsequent failures drop to debug so a sustained-down
        backend cannot flood the logs. Only ever called on the background
        loop thread, so the flag read/write needs no lock.
        """
        if not self._dispatch_failure_logged:
            self._dispatch_failure_logged = True
            logger.warning(msg, *args, exc_info=exc_info)
        else:
            logger.debug(msg, *args, exc_info=exc_info)

    def _on_future_done(self, future: concurrent.futures.Future[None]) -> None:
        """Observe the future, drop it from the pending set, release the slot.

        Uses ``future.exception()`` to observe the outcome so asyncio
        doesn't warn "exception was never retrieved" at GC time.
        ``concurrent.futures.Future.exception()`` *raises*
        ``CancelledError`` when the future was cancelled (the observe-
        without-raise semantics apply only to :class:`asyncio.Future`,
        not this ``concurrent.futures`` type), so the observation is
        wrapped in a targeted catch. The accounting — semaphore release
        and pending-set discard — runs in ``finally`` so success,
        failure, and cancellation all clean up correctly.
        """
        try:
            future.exception()
        except concurrent.futures.CancelledError:
            # Cancellation during shutdown is expected; the underlying
            # coroutine's own exception (if any) was already logged by
            # ``_run``.
            pass
        finally:
            with self._futures_lock:
                self._futures.discard(future)
            self._inflight.release()

    def shutdown(self, *, wait: bool = True, timeout: float = 5.0) -> None:
        """Stop accepting new submissions; optionally drain pending, then stop the loop.

        Call at process exit to avoid losing in-flight telemetry.
        Safe to call more than once — subsequent calls are no-ops.

        Args:
            wait: When ``True`` (default), block until pending
                coroutines finish (bounded by ``timeout``) before
                stopping the loop. When ``False``, stop immediately;
                in-flight coroutines are cancelled by the loop's
                teardown path.
            timeout: Maximum seconds to wait for pending coroutines
                when ``wait=True``. Coroutines still in flight after
                the timeout are cancelled by loop teardown. The default
                is deliberately short: the only caller is a CLI exit path,
                where a long drain against a degraded backend would just
                stall process teardown (telemetry is best-effort).
        """
        if self._shutdown_event.is_set():
            return
        self._shutdown_event.set()

        if wait:
            with self._futures_lock:
                pending = list(self._futures)
            if pending:
                concurrent.futures.wait(pending, timeout=timeout)

        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except RuntimeError:
            # Loop already stopped.
            pass
        self._loop_thread.join(timeout=5.0)
