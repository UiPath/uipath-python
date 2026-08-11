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
  loop. See "one dispatcher per provider" below.

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

        self._loop = asyncio.new_event_loop()
        self._loop_ready = threading.Event()
        self._loop_thread = threading.Thread(
            target=self._run_loop,
            name="governance-track-event-loop",
            daemon=True,
        )
        self._loop_thread.start()
        # Block until the loop is running so the first ``dispatch`` cannot
        # race with startup and hit "loop not running" errors.
        self._loop_ready.wait()

    def _run_loop(self) -> None:
        """Body of the background loop thread — runs until ``shutdown``."""
        asyncio.set_event_loop(self._loop)
        self._loop_ready.set()
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
        - **Coroutine exception**: the provider's HTTP call may raise
          for any reason (serialization, 5xx, transport). ``_run``
          catches, logs at debug with ``exc_info=True``, and the
          done-callback observes the future to suppress asyncio's
          "exception was never retrieved" warning.
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
        """Coroutine body — the async HTTP call itself."""
        try:
            await self._provider.track_event_async(
                event_name=event_name,
                data=data,
                operation_id=operation_id,
            )
        except Exception as exc:  # noqa: BLE001 - fire-and-forget contract
            logger.debug("Failed to dispatch track_event: %s", exc, exc_info=True)

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

    def shutdown(self, *, wait: bool = True, timeout: float = 30.0) -> None:
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
                the timeout are cancelled by loop teardown.
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
