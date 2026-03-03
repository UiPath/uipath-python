"""Debug wrapper for function runtimes with Python-level breakpoint support.

Provides UiPathDebugFunctionsRuntime, a delegate wrapper that adds
sys.settrace-based line-level breakpoints to any runtime.  When
breakpoints are present in the execution options the delegate's
execute() runs in a background thread with tracing enabled, yielding
UiPathBreakpointResult events that carry captured local variables for
inspection.

Composition chain (debug command):

    UiPathDebugRuntime                      -> bridge I/O, resume loop
      └─ UiPathDebugFunctionsRuntime        -> trace-based line breakpoints
           └─ UiPathFunctionsRuntime        -> loads & executes user code
"""

from __future__ import annotations

import asyncio
import contextvars
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
from uipath.runtime.events import UiPathRuntimeStateEvent, UiPathRuntimeStatePhase
from uipath.runtime.schema import UiPathRuntimeSchema

logger = logging.getLogger(__name__)

# Safety limits for local variable capture
_MAX_LOCALS = 100
_MAX_STRING_LENGTH = 10_000
_MAX_COLLECTION_ITEMS = 500

# Thread health-check interval (seconds) for wait_for_event
_EVENT_POLL_INTERVAL = 1.0

# Bitmask for generator / coroutine / async-generator code objects.
# Used to suppress spurious state events on yield/await resumption.
_CO_GENERATOR_LIKE = (
    0x20  # CO_GENERATOR
    | 0x80  # CO_COROUTINE
    | 0x200  # CO_ASYNC_GENERATOR
)


def _capture_frame_locals(frame: FrameType) -> dict[str, Any]:
    """Snapshot local variables from a live frame for variable inspection.

    Primitives and JSON-serialisable collections are kept as-is so the
    bridge can render them natively. Everything else is repr()-ed to
    guarantee safe serialisation over the wire.

    Safety guards:
    - At most ``_MAX_LOCALS`` variables captured.
    - Strings longer than ``_MAX_STRING_LENGTH`` are truncated.
    - Collections larger than ``_MAX_COLLECTION_ITEMS`` are summarised.
    """
    snapshot: dict[str, Any] = {}
    for i, (name, value) in enumerate(frame.f_locals.items()):
        if i >= _MAX_LOCALS:
            snapshot["..."] = f"<{len(frame.f_locals) - _MAX_LOCALS} more locals>"
            break
        try:
            if isinstance(value, (bool, int, float, type(None))):
                snapshot[name] = value
            elif isinstance(value, str):
                if len(value) <= _MAX_STRING_LENGTH:
                    snapshot[name] = value
                else:
                    snapshot[name] = value[:_MAX_STRING_LENGTH] + "..."
            elif isinstance(value, (dict, list, tuple)):
                if len(value) > _MAX_COLLECTION_ITEMS:
                    snapshot[name] = f"<{type(value).__name__} with {len(value)} items>"
                else:
                    # Strict probe -- no default=str, so nested non-serialisable
                    # objects (code, frame, etc.) correctly fail here.
                    json.dumps(value)
                    snapshot[name] = value
            else:
                snapshot[name] = repr(value)
        except Exception:
            try:
                r = repr(value)
                snapshot[name] = (
                    r
                    if len(r) <= _MAX_STRING_LENGTH
                    else r[:_MAX_STRING_LENGTH] + "..."
                )
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


class _FrameState:
    """Per-frame tracking for the trace callback.

    Created on ``call`` and cleaned up on ``return`` (for normal
    functions).  For generators/coroutines the state persists across
    yield/await cycles so we can suppress duplicate "started" events on
    resumption and skip "completed" on intermediate yields.
    """

    __slots__ = ("faulted", "is_generator", "last_line")

    def __init__(self, *, is_generator: bool = False) -> None:
        self.faulted: bool = False
        self.is_generator: bool = is_generator
        # Last line event seen in this frame.  Used to deduplicate the
        # bounce-back pattern where multiline expressions (e.g.
        # ``return Foo(arg=bar(...))``) cause the bytecode to revisit the
        # call-site line after evaluating arguments on deeper lines.
        # Only suppress when the *immediately preceding* line event was
        # the same breakpoint line (no intervening lines), so loop
        # iterations that pass through other lines still fire normally.
        self.last_line: int = -1


class BreakpointController:
    """Synchronises a sys.settrace-instrumented thread with an async stream.

    Lifecycle
    ---------
    1. Created with breakpoint locations and a project directory.
    2. start() launches delegate.execute() in a daemon thread with
       tracing enabled.
    3. When a matching line is reached the thread pauses and a
       ("breakpoint", ...) event is enqueued.
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
        state_tracked_functions: dict[str, set[str]] | None = None,
        node_id_map: dict[tuple[str, str], str] | None = None,
    ) -> None:
        """Initialize the controller.

        Parameters
        ----------
        state_tracked_functions:
            If provided, state events are emitted *only* for function calls
            whose ``(abs_file_path, func_name)`` appears in this mapping
            (``{abs_path: {func_name, ...}, ...}``).  When ``None``, no state
            events are emitted.
        node_id_map:
            Mapping of ``(abs_path, func_name)`` → graph node ID string
            (e.g. ``"src/main.py:5"``).  Used to set ``qualified_node_name``
            on state events so they match the graph node IDs returned by
            ``get_schema``.
        """
        self._project_dir = project_dir
        self._entrypoint_path = (
            os.path.abspath(entrypoint_path) if entrypoint_path else None
        )
        self._state_tracked: dict[str, set[str]] | None = state_tracked_functions
        self._node_id_map: dict[tuple[str, str], str] = node_id_map or {}
        self._step_mode: bool = breakpoints == "*"
        if isinstance(breakpoints, list):
            self._file_breakpoints: dict[str, set[int]] = self._build_breakpoint_map(
                breakpoints
            )
        else:
            self._file_breakpoints: dict[str, set[int]] = {}
        # Per-frame tracking.  Keyed by id(frame); created on ``call``,
        # removed on ``return`` for normal functions.  For generators the
        # state persists across yield/resume cycles.
        self._frame_states: dict[int, _FrameState] = {}
        self._events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._resume_event = threading.Event()
        self._stopped = False
        self._thread: threading.Thread | None = None
        self._abspath_cache: dict[str, str] = {}

    # Breakpoint management

    def _build_breakpoint_map(self, breakpoints: list[str]) -> dict[str, set[int]]:
        """Parse breakpoint strings into a new *file -> line-numbers* mapping.

        Returns a fresh dict (safe for atomic reference swap).

        Supported formats::

            "42"          -> line 42 in the entrypoint file
            "main.py:42"  -> line 42 in main.py (resolved relative to cwd)
            "helper"      -> resolved via node_id_map to file:line
        """
        result: dict[str, set[int]] = {}
        for bp in breakpoints:
            if ":" in bp:
                file_part, line_str = bp.rsplit(":", 1)
                try:
                    line = int(line_str)
                except ValueError:
                    continue
                resolved = os.path.abspath(file_part)
                result.setdefault(resolved, set()).add(line)
            else:
                try:
                    line = int(bp)
                except ValueError:
                    # Non-numeric token: try resolving as a function name
                    # via the node_id_map (the bridge may send bare names).
                    resolved_id = self._resolve_func_name(bp)
                    if resolved_id and ":" in resolved_id:
                        file_part, line_str = resolved_id.rsplit(":", 1)
                        try:
                            line = int(line_str)
                        except ValueError:
                            continue
                        resolved = os.path.abspath(file_part)
                        result.setdefault(resolved, set()).add(line)
                    continue
                if self._entrypoint_path is not None:
                    result.setdefault(self._entrypoint_path, set()).add(line)
        return result

    def _resolve_func_name(self, name: str) -> str | None:
        """Look up a bare function name in the node_id_map.

        Returns the ``"file:line"`` node ID if found, otherwise ``None``.
        """
        for (_, func_name), node_id in self._node_id_map.items():
            if func_name == name:
                return node_id
        return None

    def update_breakpoints(self, breakpoints: list[str] | Literal["*"] | None) -> None:
        """Replace the active breakpoint set (called between resume cycles).

        Builds a new dict and swaps the reference atomically so the trace
        thread never sees a partially-cleared mapping.
        """
        self._step_mode = breakpoints == "*"
        if isinstance(breakpoints, list):
            self._file_breakpoints = self._build_breakpoint_map(breakpoints)
        else:
            self._file_breakpoints = {}

    # Tracing

    def _abspath(self, path: str) -> str:
        """Cached os.path.abspath to avoid repeated resolution in the hot path."""
        result = self._abspath_cache.get(path)
        if result is None:
            result = os.path.abspath(path)
            self._abspath_cache[path] = result
        return result

    def _is_project_file(self, abspath: str) -> bool:
        """Return *True* for real .py files under the project directory."""
        return (
            abspath.endswith(".py")
            and abspath.startswith(self._project_dir)
            and "site-packages" not in abspath
        )

    def _is_tracked_function(self, abspath: str, func_name: str) -> bool:
        """Return *True* if this function should produce a state event."""
        if self._state_tracked is None:
            return False
        funcs = self._state_tracked.get(abspath)
        return funcs is not None and func_name in funcs

    def _trace_callback(self, frame: FrameType, event: str, arg: Any) -> Any:
        """sys.settrace callback -- dispatched for every frame event."""
        if self._stopped:
            return None

        try:
            co_filename = frame.f_code.co_filename
            # Fast reject: frozen/built-in modules never have a dot-py path
            if co_filename.startswith("<"):
                return None

            filepath = self._abspath(co_filename)

            if event == "call":
                is_project = self._is_project_file(filepath)

                # Decide whether to trace *into* this frame FIRST.
                # We only get "return" events for traced frames, so we
                # must not create _FrameState for frames we won't trace
                # (their state would leak and poison future frame-id reuse).
                trace_into = False
                if self._step_mode:
                    trace_into = is_project
                elif filepath in self._file_breakpoints:
                    trace_into = True
                elif is_project and filepath in (self._state_tracked or {}):
                    trace_into = True

                if not trace_into:
                    return None

                frame_id = id(frame)
                func_name = frame.f_code.co_name
                is_gen = bool(frame.f_code.co_flags & _CO_GENERATOR_LIKE)

                existing = self._frame_states.get(frame_id)
                if existing is not None and existing.is_generator:
                    # Generator/coroutine resumption after yield/await.
                    # Don't emit a duplicate "started" event and don't
                    # reset the fault tracker.
                    pass
                else:
                    # Fresh frame (or a reused id from a deallocated frame).
                    state = _FrameState(is_generator=is_gen)
                    self._frame_states[frame_id] = state

                    # Emit "started" state event for tracked functions.
                    if is_project and self._is_tracked_function(filepath, func_name):
                        node_id = self._node_id_map.get((filepath, func_name))
                        self._events.put(
                            (
                                "state",
                                {
                                    "file": filepath,
                                    "line": frame.f_lineno,
                                    "function": func_name,
                                    "locals": _capture_frame_locals(frame),
                                    "phase": "started",
                                    "node_id": node_id,
                                },
                            )
                        )

                return self._trace_callback

            if event == "line":
                # Skip module-level lines (imports, class/function defs).
                # These fire during module loading, not user code execution.
                if frame.f_code.co_name == "<module>":
                    return self._trace_callback

                lineno = frame.f_lineno
                # Update last_line for bounce-back dedup (see _FrameState).
                state = self._frame_states.get(id(frame))
                prev_line = state.last_line if state is not None else -1
                if state is not None:
                    state.last_line = lineno

                should_break = (
                    self._step_mode and self._is_project_file(filepath)
                ) or (lineno in self._file_breakpoints.get(filepath, ()))

                if should_break:
                    # Deduplicate: multiline expressions (e.g.
                    # ``return Foo(arg=bar(...))``) cause the bytecode to
                    # bounce back to the call-site line after evaluating
                    # arguments on deeper lines.  Without this guard the
                    # same breakpoint would fire twice per call.
                    # Only suppress when the *immediately preceding* line
                    # event was the same line (no intervening lines), so
                    # loop iterations still fire normally.
                    if lineno == prev_line:
                        return self._trace_callback

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

            elif event == "exception":
                # Record that this frame saw an unhandled exception so the
                # "return" handler can emit "faulted" instead of "completed".
                if self._is_project_file(filepath) and self._is_tracked_function(
                    filepath, frame.f_code.co_name
                ):
                    state = self._frame_states.get(id(frame))
                    if state is not None:
                        state.faulted = True

            elif event == "return":
                frame_id = id(frame)
                func_name = frame.f_code.co_name
                state = self._frame_states.get(frame_id)

                # Generator/coroutine frames: don't pop state or emit
                # "completed" on yield/await -- the frame is merely
                # suspended, not finished.
                if state is not None and state.is_generator:
                    pass  # state persists for the next resumption
                else:
                    # Normal function: pop state and emit terminal event.
                    state = self._frame_states.pop(frame_id, None)
                    if self._is_project_file(filepath) and self._is_tracked_function(
                        filepath, func_name
                    ):
                        saw_exception = state is not None and state.faulted

                        # Exception propagated (arg is None on unhandled raise)
                        if saw_exception and arg is None:
                            phase = "faulted"
                        else:
                            phase = "completed"

                        node_id = self._node_id_map.get((filepath, func_name))
                        locals_snapshot = _capture_frame_locals(frame)
                        if arg is not None:
                            try:
                                import json as _json

                                _json.dumps(arg)
                                locals_snapshot["__return__"] = arg
                            except Exception:
                                locals_snapshot["__return__"] = repr(arg)
                        self._events.put(
                            (
                                "state",
                                {
                                    "file": filepath,
                                    "line": frame.f_lineno,
                                    "function": func_name,
                                    "locals": locals_snapshot,
                                    "phase": phase,
                                    "node_id": node_id,
                                },
                            )
                        )

            return self._trace_callback

        except Exception:
            # Never let our own errors propagate -- that would disable tracing.
            logger.debug("Error in trace callback", exc_info=True)
            return self._trace_callback

    # Thread lifecycle

    def start(
        self,
        delegate: UiPathRuntimeProtocol,
        input: dict[str, Any] | None,
        options: UiPathExecuteOptions | None,
    ) -> None:
        """Launch delegate.execute() in a traced daemon thread.

        Copies the caller's contextvars (including OTEL span context) so
        that ``@traced`` decorators in user code produce spans that are
        properly linked to the parent trace.
        """
        ctx = contextvars.copy_context()
        self._thread = threading.Thread(
            target=ctx.run,
            args=(self._run, delegate, input, options),
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
        loop = asyncio.new_event_loop()
        try:
            sys.settrace(self._trace_callback)
            try:
                result = loop.run_until_complete(delegate.execute(input, options))
            finally:
                sys.settrace(None)
            self._events.put(("completed", result))
        except Exception as exc:
            self._events.put(("error", exc))
        finally:
            # Cancel any lingering tasks so loop.close() doesn't warn.
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            loop.close()

    # Inter-thread communication

    def wait_for_event(self) -> tuple[str, Any]:
        """Block until the next breakpoint hit or execution completion.

        Periodically checks that the trace thread is still alive so callers
        do not hang indefinitely if the thread dies unexpectedly (e.g. via
        ``SystemExit`` or a C-extension segfault).
        """
        while True:
            try:
                return self._events.get(timeout=_EVENT_POLL_INTERVAL)
            except queue.Empty:
                if self._thread is not None and not self._thread.is_alive():
                    raise RuntimeError(
                        "Trace thread died without producing a terminal event"
                    )

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

    When breakpoints **are** present the delegate's execute() runs in
    a background thread with sys.settrace enabled.  The trace callback
    pauses the thread at matching lines and this runtime yields
    UiPathBreakpointResult events with captured local variables.

    Additionally emits ``UiPathRuntimeStateEvent`` for every function call
    that appears in the entrypoint's call graph, so the debug bridge can
    visualise execution flow through the graph nodes.

    Works for both sync and async user functions -- async functions run in
    a dedicated asyncio event loop on the background thread.

    Parameters
    ----------
    delegate:
        The inner runtime to wrap (typically UiPathFunctionsRuntime).
    entrypoint_path:
        Absolute or relative path to the user's entrypoint file.  Used to
        resolve bare line-number breakpoints (e.g. "42").
    function_name:
        Name of the entrypoint function.  Used together with
        *entrypoint_path* to build the call graph for state events.
    """

    def __init__(
        self,
        delegate: UiPathRuntimeProtocol,
        entrypoint_path: str | None = None,
        function_name: str | None = None,
    ) -> None:
        """Initialize the debug wrapper."""
        self.delegate = delegate
        self._entrypoint_path = entrypoint_path
        self._function_name = function_name
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

        Emits ``UiPathRuntimeStateEvent`` for every call-graph function
        entry so the debug bridge can visualise execution flow.

        Breakpoint formats (via options.breakpoints):

        * "42"          -- line 42 in the entrypoint file
        * "main.py:42"  -- line 42 in *main.py* (resolved from cwd)
        * "*"           -- **step mode**: break on every line in project files
        """
        breakpoints = options.breakpoints if options else None

        # Resume from a previous breakpoint
        if options and options.resume and self._controller is not None:
            self._controller.update_breakpoints(breakpoints)
            self._controller.resume()

            async for event in self._drain_events():
                yield event
            return

        # Build the set of tracked functions from the call graph so we
        # can emit state events even without breakpoints.
        tracked, node_id_map = self._build_tracked_functions()

        # Nothing to trace -> transparent delegation.  The controller
        # path runs delegate.execute() in a background thread with a
        # new asyncio event loop, so we only use it when there is
        # something to observe (breakpoints and/or state tracking).
        if not breakpoints and not tracked:
            async for event in self.delegate.stream(input, options):
                yield event
            return

        controller = BreakpointController(
            project_dir=str(Path.cwd()),
            breakpoints=breakpoints if breakpoints else [],
            entrypoint_path=self._entrypoint_path,
            state_tracked_functions=tracked,
            node_id_map=node_id_map,
        )
        self._controller = controller

        # Strip breakpoints from the options forwarded to the delegate --
        # the delegate does not handle them; we do via the trace.
        delegate_options = UiPathExecuteOptions(
            resume=options.resume if options else False,
        )
        controller.start(self.delegate, input, delegate_options)

        async for event in self._drain_events():
            yield event

    async def get_schema(self) -> UiPathRuntimeSchema:
        """Pass-through to delegate."""
        return await self.delegate.get_schema()

    async def dispose(self) -> None:
        """Clean up the trace thread and delegate resources."""
        if self._controller is not None:
            self._controller.stop()
            self._controller = None
        await self.delegate.dispose()

    def _build_tracked_functions(
        self,
    ) -> tuple[dict[str, set[str]] | None, dict[tuple[str, str], str]]:
        """Build tracked-function and node-ID mappings from the call graph.

        Returns:
        -------
        tracked:
            ``{abs_path: {func_name, ...}}`` or ``None`` when the graph
            cannot be built.
        node_id_map:
            ``{(abs_path, func_name): node_id}`` so the trace callback
            can set ``qualified_node_name`` to match the graph node IDs
            returned by ``get_schema``.
        """
        if not self._entrypoint_path or not self._function_name:
            return None, {}

        try:
            from .graph_builder import build_call_graph

            graph = build_call_graph(
                self._entrypoint_path,
                self._function_name,
                project_dir=str(Path.cwd()),
            )

            tracked: dict[str, set[str]] = {}
            node_id_map: dict[tuple[str, str], str] = {}
            for node in graph.nodes:
                file_rel = (node.metadata or {}).get("file")
                if not file_rel:
                    continue
                abs_path = os.path.abspath(file_rel)
                tracked.setdefault(abs_path, set()).add(node.name)
                node_id_map[(abs_path, node.name)] = node.id

            return (tracked if tracked else None), node_id_map
        except Exception:
            logger.debug("Failed to build call graph for state tracking", exc_info=True)
            return None, {}

    async def _drain_events(self) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Drain events from the controller, yielding state events and stopping at a terminal event."""
        while self._controller is not None:
            event_type, data = await asyncio.to_thread(self._controller.wait_for_event)
            if event_type == "state":
                yield self._to_state_event(data)
            else:
                yield self._to_runtime_event(event_type, data)
                return

    @staticmethod
    def _to_state_event(data: dict[str, Any]) -> UiPathRuntimeStateEvent:
        """Convert a trace state event into a UiPathRuntimeStateEvent."""
        phase = UiPathRuntimeStatePhase(data.get("phase", "updated"))
        # Use the pre-resolved graph node ID when available so the client
        # can map state events to graph nodes.  Falls back to the raw
        # file:line from the frame (which may differ from the graph ID
        # because frame.f_lineno on "call" is the def line, not the
        # first-code-line used by the graph builder).
        node_id = data.get("node_id")
        qualified = node_id if node_id else _format_location(data["file"], data["line"])
        return UiPathRuntimeStateEvent(
            node_name=data["function"],
            qualified_node_name=qualified,
            payload=data["locals"],
            phase=phase,
        )

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
