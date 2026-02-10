"""Debug wrapper for function runtimes with Python-level breakpoint support.

Provides UiPathDebugFunctionsRuntime, a delegate wrapper that adds
sys.settrace-based line-level breakpoints to any runtime.  When
breakpoints are present in the execution options the delegate's
execute() runs in a background thread with tracing enabled, yielding
UiPathBreakpointResult events that carry captured local variables for
inspection.

Composition chain (debug command):

    UiPathDebugRuntime                      → bridge I/O, resume loop
      └─ UiPathDebugFunctionsRuntime        → trace-based line breakpoints
           └─ UiPathFunctionsRuntime        → loads & executes user code
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import sys
import threading
from pathlib import Path
from types import FrameType
from typing import Any, AsyncGenerator, Literal

from uipath.runtime import (
    UiPathBreakpointResult,
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
    UiPathStreamOptions,
)
from uipath.runtime.schema import UiPathRuntimeSchema

logger = logging.getLogger(__name__)


def _capture_frame_locals(frame: FrameType) -> dict[str, Any]:
    """Snapshot local variables from a live frame for variable inspection.

    Primitives and JSON-serialisable collections are kept as-is so the
    bridge can render them natively. Everything else is repr()-ed to
    guarantee safe serialisation over the wire.
    """
    snapshot: dict[str, Any] = {}
    for name, value in frame.f_locals.items():
        try:
            if isinstance(value, (bool, int, float, str, type(None))):
                snapshot[name] = value
            elif isinstance(value, (dict, list, tuple)):
                json.dumps(value, default=str)  # serialisability probe
                snapshot[name] = value
            else:
                snapshot[name] = repr(value)
        except Exception:
            try:
                snapshot[name] = repr(value)
            except Exception:
                snapshot[name] = "<unrepresentable>"
    return snapshot


def _format_location(filepath: str, line: int) -> str:
    """Return a human-readable file:line breakpoint identifier."""
    try:
        relative = Path(filepath).relative_to(Path.cwd())
    except ValueError:
        relative = Path(Path(filepath).name)
    return f"{relative}:{line}"


class BreakpointController:
    """Synchronises a sys.settrace-instrumented thread with an async stream.

    Lifecycle
    ---------
    1. Created with breakpoint locations and a project directory.
    2. start() launches delegate.execute() in a daemon thread with
       tracing enabled.
    3. When a matching line is reached the thread pauses and a
       ("breakpoint", …) event is enqueued.
    4. The async stream dequeues the event and yields a
       UiPathBreakpointResult.
    5. resume() unblocks the thread so it continues to the next
       breakpoint or completion.
    6. stop() terminates the thread gracefully.
    """

    def __init__(
        self,
        project_dir: str,
        breakpoints: list[str] | Literal["*"],
        entrypoint_path: str | None = None,
    ) -> None:
        """Initialize the controller with project directory, breakpoints, and optional entrypoint path."""
        self._project_dir = project_dir
        self._entrypoint_path = (
            os.path.abspath(entrypoint_path) if entrypoint_path else None
        )
        self._step_mode: bool = breakpoints == "*"
        self._file_breakpoints: dict[str, set[int]] = {}
        if isinstance(breakpoints, list):
            self._parse_breakpoints(breakpoints)

        self._events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._resume_event = threading.Event()
        self._stopped = False
        self._thread: threading.Thread | None = None
        self._abspath_cache: dict[str, str] = {}

    # Breakpoint management

    def _parse_breakpoints(self, breakpoints: list[str]) -> None:
        """Parse breakpoint strings into *file → line-numbers* mappings.

        Supported formats::

            "42"          → line 42 in the entrypoint file
            "main.py:42"  → line 42 in main.py (resolved relative to cwd)
        """
        for bp in breakpoints:
            if ":" in bp:
                file_part, line_str = bp.rsplit(":", 1)
                try:
                    line = int(line_str)
                except ValueError:
                    continue
                resolved = os.path.abspath(file_part)
                self._file_breakpoints.setdefault(resolved, set()).add(line)
            else:
                try:
                    line = int(bp)
                except ValueError:
                    continue  # non-numeric tokens (agent node names) are ignored
                if self._entrypoint_path is not None:
                    self._file_breakpoints.setdefault(self._entrypoint_path, set()).add(
                        line
                    )

    def update_breakpoints(self, breakpoints: list[str] | Literal["*"] | None) -> None:
        """Replace the active breakpoint set (called between resume cycles)."""
        self._step_mode = breakpoints == "*"
        self._file_breakpoints.clear()
        if isinstance(breakpoints, list):
            self._parse_breakpoints(breakpoints)

    # Tracing

    def _abspath(self, path: str) -> str:
        """Cached os.path.abspath to avoid repeated resolution in the hot path."""
        result = self._abspath_cache.get(path)
        if result is None:
            result = os.path.abspath(path)
            self._abspath_cache[path] = result
        return result

    def _is_project_file(self, abspath: str) -> bool:
        """Return *True* for files under the project directory that are not vendored."""
        return abspath.startswith(self._project_dir) and "site-packages" not in abspath

    def _trace_callback(self, frame: FrameType, event: str, arg: Any) -> Any:
        """sys.settrace callback — dispatched for every frame event."""
        if self._stopped:
            return None

        try:
            filepath = self._abspath(frame.f_code.co_filename)

            if event == "call":
                # Decide whether to trace *into* this function's frame.
                if self._step_mode:
                    return (
                        self._trace_callback
                        if self._is_project_file(filepath)
                        else None
                    )
                return (
                    self._trace_callback if filepath in self._file_breakpoints else None
                )

            if event == "line":
                lineno = frame.f_lineno
                should_break = (
                    self._step_mode and self._is_project_file(filepath)
                ) or (lineno in self._file_breakpoints.get(filepath, ()))

                if should_break:
                    self._events.put(
                        (
                            "breakpoint",
                            {
                                "file": filepath,
                                "line": lineno,
                                "function": frame.f_code.co_name,
                                "locals": _capture_frame_locals(frame),
                            },
                        )
                    )
                    # Pause the thread until the bridge signals resume.
                    self._resume_event.wait()
                    self._resume_event.clear()

                    if self._stopped:
                        return None

            return self._trace_callback

        except Exception:
            # Never let our own errors propagate — that would disable tracing.
            return self._trace_callback

    # Thread lifecycle

    def start(
        self,
        delegate: UiPathRuntimeProtocol,
        input: dict[str, Any] | None,
        options: UiPathExecuteOptions | None,
    ) -> None:
        """Launch delegate.execute() in a traced daemon thread."""
        self._thread = threading.Thread(
            target=self._run,
            args=(delegate, input, options),
            daemon=True,
        )
        self._thread.start()

    def _run(
        self,
        delegate: UiPathRuntimeProtocol,
        input: dict[str, Any] | None,
        options: UiPathExecuteOptions | None,
    ) -> None:
        """Thread entry-point: install the trace, execute, report result."""
        try:
            sys.settrace(self._trace_callback)
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(delegate.execute(input, options))
            finally:
                loop.close()
            sys.settrace(None)
            self._events.put(("completed", result))
        except Exception as exc:
            sys.settrace(None)
            self._events.put(("error", exc))

    # Inter-thread communication

    def wait_for_event(self) -> tuple[str, Any]:
        """Block until the next breakpoint hit or execution completion."""
        return self._events.get()

    def resume(self) -> None:
        """Unblock the trace thread so it continues past the current breakpoint."""
        self._resume_event.set()

    def stop(self) -> None:
        """Terminate the controller and join the background thread."""
        self._stopped = True
        self._resume_event.set()  # unblock if paused at a breakpoint
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)


class UiPathDebugFunctionsRuntime:
    """Delegate wrapper that adds Python-level breakpoint support via sys.settrace.

    Follows the same composition pattern as UiPathDebugRuntime: wraps a UiPathRuntimeProtocol delegate and
    intercepts stream() to inject breakpoint behaviour.

    When no breakpoints are active every call delegates transparently.
    When breakpoints **are** present the delegate's execute() runs in
    a background thread with sys.settrace enabled.  The trace callback
    pauses the thread at matching lines and this runtime yields
    UiPathBreakpointResult events with captured local variables.

    Works for both sync and async user functions — async functions run in
    a dedicated asyncio event loop on the background thread.

    Parameters
    ----------
    delegate:
        The inner runtime to wrap (typically UiPathFunctionsRuntime).
    entrypoint_path:
        Absolute or relative path to the user's entrypoint file.  Used to
        resolve bare line-number breakpoints (e.g. "42").
    """

    def __init__(
        self,
        delegate: UiPathRuntimeProtocol,
        entrypoint_path: str | None = None,
    ) -> None:
        """Initialize the debug wrapper with a delegate runtime and optional entrypoint path."""
        self.delegate = delegate
        self._entrypoint_path = entrypoint_path
        self._controller: BreakpointController | None = None

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        """Pass-through to delegate (no breakpoint support outside stream)."""
        return await self.delegate.execute(input, options)

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Stream execution events with line-level breakpoint support.

        Breakpoint formats (via options.breakpoints):

        * "42"          — line 42 in the entrypoint file
        * "main.py:42"  — line 42 in *main.py* (resolved from cwd)
        * "*"           — **step mode**: break on every line in project files
        """
        breakpoints = options.breakpoints if options else None

        # Resume from a previous breakpoint
        if options and options.resume and self._controller is not None:
            self._controller.update_breakpoints(breakpoints)
            self._controller.resume()

            event_type, data = await asyncio.to_thread(self._controller.wait_for_event)
            yield self._to_runtime_event(event_type, data)
            return

        # No breakpoints, transparent delegation
        if not breakpoints:
            async for event in self.delegate.stream(input, options):
                yield event
            return

        # First execution with breakpoints
        controller = BreakpointController(
            project_dir=str(Path.cwd()),
            breakpoints=breakpoints,
            entrypoint_path=self._entrypoint_path,
        )
        self._controller = controller

        # Strip breakpoints from the options forwarded to the delegate —
        # the delegate does not handle them; we do via the trace.
        delegate_options = UiPathExecuteOptions(
            resume=options.resume if options else False,
        )
        controller.start(self.delegate, input, delegate_options)

        event_type, data = await asyncio.to_thread(controller.wait_for_event)
        yield self._to_runtime_event(event_type, data)

    async def get_schema(self) -> UiPathRuntimeSchema:
        """Pass-through to delegate."""
        return await self.delegate.get_schema()

    async def dispose(self) -> None:
        """Clean up the trace thread and delegate resources."""
        if self._controller is not None:
            self._controller.stop()
            self._controller = None
        await self.delegate.dispose()

    def _to_runtime_event(self, event_type: str, data: Any) -> UiPathRuntimeEvent:
        """Convert a BreakpointController event into a UiPathRuntimeEvent."""
        if event_type == "breakpoint":
            return UiPathBreakpointResult(
                breakpoint_node=_format_location(data["file"], data["line"]),
                breakpoint_type="before",
                current_state=data["locals"],
                next_nodes=[],
            )

        # Terminal events, release the controller.
        self._controller = None

        if event_type == "completed":
            # data is already a UiPathRuntimeResult from delegate.execute().
            return data

        # "error", re-raise so UiPathDebugRuntime can emit_execution_error().
        raise data
