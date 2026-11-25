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
import contextvars
import json
import logging
import os
import queue
import sys
import threading
from contextlib import aclosing
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
                # Strict probe — no default=str, so nested non-serialisable
                # objects (code, frame, etc.) correctly fail here.
                json.dumps(value)
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


async def _wait_out(future: asyncio.Future[Any]) -> None:
    """Wait until ``future`` is done, through cancellations of the caller, then re-raise the last."""
    try:
        await asyncio.wait({future})
    except asyncio.CancelledError:
        await _wait_out(future)
        raise


class _StopOnceTask(asyncio.Task[Any]):
    """A task that ignores cancellation once the debug stop has reached it.

    The stop ends it like a cancellation. The task groups and awaits it belongs
    to would cancel it again when the stop reaches them, cutting its cleanup
    short.
    """

    stopped = False

    def cancel(self, msg: Any | None = None) -> bool:
        if self.stopped:
            return False
        return super().cancel(msg)


def _new_stop_once_task(
    loop: asyncio.AbstractEventLoop, coro: Any, **kwargs: Any
) -> asyncio.Task[Any]:
    return _StopOnceTask(coro, loop=loop, **kwargs)


def _is_debugger_tracer(tracer: object) -> bool:
    """Return True if *tracer* is the trace function of a pydevd-based debugger.

    debugpy (VS Code) and PyCharm are built on pydevd, which traces threads
    through sys.settrace before Python 3.12. Installing our own trace function
    on a thread replaces theirs, so their breakpoints are never hit there. From
    Python 3.12 debugpy uses sys.monitoring and leaves sys.gettrace() empty.
    """
    if tracer is None:
        return False
    module = getattr(tracer, "__module__", None) or type(tracer).__module__
    return "pydevd" in str(module)


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
    6. request_stop() ends the execution where it is, and join() waits
       for its thread; stop() does both.
    """

    def __init__(
        self,
        project_dir: str,
        breakpoints: list[str] | Literal["*"],
        entrypoint_path: str | None = None,
        state_tracked_functions: dict[str, set[str]] | None = None,
    ) -> None:
        """Initialize the controller.

        Parameters
        ----------
        state_tracked_functions:
            If provided, state events are emitted *only* for function calls
            whose ``(abs_file_path, func_name)`` appears in this mapping
            (``{abs_path: {func_name, …}, …}``).  When ``None``, no state
            events are emitted.
        """
        self._project_dir = project_dir
        self._entrypoint_path = (
            os.path.abspath(entrypoint_path) if entrypoint_path else None
        )
        self._step_mode: bool = breakpoints == "*"
        self._file_breakpoints: dict[str, set[int]] = {}
        if isinstance(breakpoints, list):
            self._parse_breakpoints(breakpoints)

        self._state_tracked: dict[str, set[str]] | None = state_tracked_functions
        self._events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._resume_event = threading.Event()
        self._stopped = False
        # Touched only on the execution's thread: by the trace and by the loop.
        self._stopped_tasks: set[asyncio.Task[Any]] = set()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task[Any] | None = None
        self._lock = threading.Lock()
        self._abspath_cache: dict[str, str] = {}
        # Track which breakpoints already fired per frame so that
        # multiline expressions (where the bytecodes bounce back to the
        # call line after evaluating arguments on deeper lines) don't
        # trigger the same breakpoint twice within one function call.
        self._hit_lines: dict[int, set[int]] = {}  # frame-id → {lines}

    # Breakpoint management

    def _parse_breakpoints(self, breakpoints: list[str]) -> None:
        """Parse breakpoint strings into *file → line-numbers* mappings.

        Supported formats:

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
        """sys.settrace callback — dispatched for every frame event."""
        if self._stopped:
            return self._stop_in(frame, event, arg)

        try:
            co_filename = frame.f_code.co_filename
            # Fast reject: frozen/built-in modules never have a dot-py path
            if co_filename.startswith("<"):
                return None

            filepath = self._abspath(co_filename)

            if event == "call":
                is_project = self._is_project_file(filepath)

                # Emit state event only for tracked graph-node functions
                if is_project and self._is_tracked_function(
                    filepath, frame.f_code.co_name
                ):
                    self._events.put(
                        (
                            "state",
                            {
                                "file": filepath,
                                "line": frame.f_lineno,
                                "function": frame.f_code.co_name,
                                "locals": _capture_frame_locals(frame),
                                "phase": "started",
                            },
                        )
                    )

                # Reset per-frame hit tracking so each call starts fresh.
                self._hit_lines[id(frame)] = set()

                # Trace into every project frame, also those outside the call
                # graph, so that a stop reaches a loop running in any of them.
                if is_project or filepath in self._file_breakpoints:
                    return self._trace_callback
                return None

            if event == "line":
                # Skip module-level lines (imports, class/function defs).
                # These fire during module loading, not user code execution.
                if frame.f_code.co_name == "<module>":
                    return self._trace_callback

                lineno = frame.f_lineno
                should_break = (
                    self._step_mode and self._is_project_file(filepath)
                ) or (lineno in self._file_breakpoints.get(filepath, ()))

                if should_break:
                    # Deduplicate: multiline expressions (e.g.
                    # ``return Foo(arg=bar(...))``) cause the bytecode to
                    # bounce back to the call-site line after evaluating
                    # arguments on deeper lines. Without this guard the
                    # same breakpoint would fire twice per call.
                    frame_hits = self._hit_lines.get(id(frame))
                    if frame_hits is not None and lineno in frame_hits:
                        return self._trace_callback
                    if frame_hits is not None:
                        frame_hits.add(lineno)

                    self._events.put(
                        (
                            "breakpoint",
                            {
                                "file": filepath,
                                "line": lineno,
                                "function": frame.f_code.co_name,
                                "function_start_line": frame.f_code.co_firstlineno,
                                "locals": _capture_frame_locals(frame),
                            },
                        )
                    )
                    # Pause the thread until the bridge signals resume.
                    self._resume_event.wait()
                    self._resume_event.clear()

                    if self._stopped:
                        return self._stop_in(frame, event, arg)

            elif event == "return":
                # Emit a "completed" state event for tracked functions
                if self._is_project_file(filepath) and self._is_tracked_function(
                    filepath, frame.f_code.co_name
                ):
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
                                "function": frame.f_code.co_name,
                                "locals": locals_snapshot,
                                "phase": "completed",
                            },
                        )
                    )
                # Clean up per-frame tracking when the frame exits.
                self._hit_lines.pop(id(frame), None)

            return self._trace_callback

        except Exception:
            # Never let our own errors propagate — that would disable tracing.
            return self._trace_callback

    def _stop_in(self, frame: FrameType, event: str, arg: Any) -> Any:
        """Stop the task running the user's code; let library and interpreter frames run.

        Raising in the event loop's own frames would break the loop instead of
        ending the function. Each task gets the stop once, so its cleanup runs
        as after an ordinary cancellation.
        """
        filename = frame.f_code.co_filename
        loop = self._loop
        if (
            loop is None
            or filename.startswith("<")
            or not self._is_project_file(self._abspath(filename))
        ):
            return None
        task = asyncio.current_task(loop)
        if task is None or task in self._stopped_tasks:
            return None
        if task.cancelling():
            # Its cancellation stops it; look again if it swallows that one.
            return self._trace_callback
        if event == "exception" and issubclass(arg[0], asyncio.CancelledError):
            # It is unwinding the stop of a task it awaits.
            self._mark_stopped(task)
            return None
        if event != "line":
            # A coroutine's resumption is a "call" event, and raising there
            # would skip its exception handlers.
            return self._trace_callback
        self._mark_stopped(task)
        self._retrace_at_next_call()
        raise asyncio.CancelledError("Debug session stopped")

    def _retrace_at_next_call(self) -> None:
        """Set the trace again at the thread's next call or return.

        A trace function that raises is unset for the whole thread, and the
        function's other tasks still need it to stop where they run. The task
        that raised calls or returns before the loop runs any other.
        """
        previous = sys.getprofile()

        def retrace(frame: FrameType, event: str, arg: Any) -> None:
            sys.setprofile(previous)
            sys.settrace(self._trace_callback)

        sys.setprofile(retrace)

    def _mark_stopped(self, task: asyncio.Task[Any]) -> None:
        self._stopped_tasks.add(task)
        if isinstance(task, _StopOnceTask):
            task.stopped = True

    def _cancel_task(self) -> None:
        """Stop the function's own task, unless the stop already reached it."""
        task = self._task
        if task is None or task in self._stopped_tasks:
            return
        task.cancel()
        self._mark_stopped(task)

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
        try:
            result = self._execute_traced(delegate, input, options)
        except (Exception, asyncio.CancelledError) as exc:
            # Also after a stop: a stream that stopped waiting still has a
            # wait_for_event() call blocked on the queue.
            self._events.put(("error", exc))
        else:
            self._events.put(("completed", result))

    def _execute_traced(
        self,
        delegate: UiPathRuntimeProtocol,
        input: dict[str, Any] | None,
        options: UiPathExecuteOptions | None,
    ) -> UiPathRuntimeResult:
        previous_tracer = sys.gettrace()
        sys.settrace(self._trace_callback)
        loop = asyncio.new_event_loop()
        loop.set_task_factory(_new_stop_once_task)
        try:
            task = loop.create_task(delegate.execute(input, options))
            with self._lock:
                self._loop, self._task = loop, task
                if self._stopped:
                    self._cancel_task()
            return loop.run_until_complete(task)
        finally:
            sys.settrace(previous_tracer)
            with self._lock:
                self._loop = self._task = None
            self._stopped_tasks.clear()
            loop.close()

    # Inter-thread communication

    def wait_for_event(self) -> tuple[str, Any]:
        """Block until the next breakpoint hit or execution completion."""
        return self._events.get()

    def resume(self) -> None:
        """Unblock the trace thread so it continues past the current breakpoint."""
        self._resume_event.set()

    def request_stop(self) -> None:
        """End the execution where it is, without waiting for it.

        A function paused at a breakpoint stops there. A running one stops at
        its next line in the project's files, or at the await it is waiting
        in, whichever comes first. Each of its tasks gets the stop once, so
        the task groups and awaits a stopped task belongs to wait for its
        cleanup. Code blocked outside Python stops once it returns.
        """
        with self._lock:
            self._stopped = True
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._cancel_task)
        self._resume_event.set()

    def join(self, timeout: float | None = None) -> None:
        """Wait for the execution's thread to end."""
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout)

    def stop(self) -> None:
        """End the execution and wait up to 5 seconds for its thread."""
        self.request_stop()
        self.join(timeout=5.0)


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
    visualise execution flow through the graph nodes.  Without breakpoints,
    these are skipped while a debugger traces the process through
    sys.settrace (debugpy before Python 3.12), so its breakpoints still hit.

    Works for both sync and async user functions — async functions run in
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

        * "42"          — line 42 in the entrypoint file
        * "main.py:42"  — line 42 in *main.py* (resolved from cwd)
        * "*"           — **step mode**: break on every line in project files
        """
        breakpoints = options.breakpoints if options else None

        # Resume from a previous breakpoint
        if options and options.resume and self._controller is not None:
            self._controller.update_breakpoints(breakpoints)
            self._controller.resume()

            async with aclosing(self._drain_events(self._controller)) as events:
                async for event in events:
                    yield event
            return

        # Build the set of tracked functions from the call graph so we
        # can emit state events even without breakpoints.
        tracked = self._build_tracked_functions()

        # A debugger tracing this thread through sys.settrace (debugpy before
        # Python 3.12) loses the worker thread to our trace function and never
        # hits its breakpoints there.
        if _is_debugger_tracer(sys.gettrace()):
            if breakpoints:
                # Our breakpoints need our trace function, so say why the
                # debugger's breakpoints stop working.
                logger.warning(
                    "Breakpoints from the debug bridge replace the attached "
                    "debugger's trace function on the thread that runs the "
                    "function, so the debugger's breakpoints won't be hit. "
                    "Clear the bridge breakpoints to use the debugger's."
                )
            elif tracked:
                # Without breakpoints of ours, state events are all we would
                # trace, so skip them and leave the debugger in charge.
                logger.debug("A debugger traces this thread; skipping state events")
                tracked = None

        # Nothing to trace → transparent delegation.  The controller
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
        )
        self._controller = controller

        # Strip breakpoints from the options forwarded to the delegate —
        # the delegate does not handle them; we do via the trace.
        delegate_options = UiPathExecuteOptions(
            resume=options.resume if options else False,
        )
        controller.start(self.delegate, input, delegate_options)

        async with aclosing(self._drain_events(controller)) as events:
            async for event in events:
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

    def _build_tracked_functions(self) -> dict[str, set[str]] | None:
        """Build a mapping of abs_file → {func_names} from the call graph.

        Returns None when the graph cannot be built (missing path / name).
        """
        if not self._entrypoint_path or not self._function_name:
            return None

        try:
            from .graph_builder import build_call_graph

            graph = build_call_graph(
                self._entrypoint_path,
                self._function_name,
                project_dir=str(Path.cwd()),
            )

            tracked: dict[str, set[str]] = {}
            for node in graph.nodes:
                file_rel = (node.metadata or {}).get("file")
                if not file_rel:
                    continue
                abs_path = os.path.abspath(file_rel)
                tracked.setdefault(abs_path, set()).add(node.name)

            return tracked if tracked else None
        except Exception:
            logger.debug("Failed to build call graph for state tracking", exc_info=True)
            return None

    async def _drain_events(
        self, controller: BreakpointController
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Drain events from the controller, yielding state events and stopping at a terminal event.

        Closed or cancelled before it gets that far, it ends the execution and
        waits for its thread, so a caller that stops consuming the stream knows
        the function no longer runs.
        """
        drained = False
        try:
            while True:
                event_type, data = await asyncio.to_thread(controller.wait_for_event)
                if event_type == "state":
                    yield self._to_state_event(data)
                    continue
                yield self._to_runtime_event(event_type, data)
                drained = True
                return
        finally:
            if not drained:
                await self._stop_execution(controller)

    async def _stop_execution(self, controller: BreakpointController) -> None:
        controller.request_stop()
        try:
            await _wait_out(asyncio.ensure_future(asyncio.to_thread(controller.join)))
        finally:
            if self._controller is controller:
                self._controller = None

    @staticmethod
    def _to_state_event(data: dict[str, Any]) -> UiPathRuntimeStateEvent:
        """Convert a trace state event into a UiPathRuntimeStateEvent."""
        phase = UiPathRuntimeStatePhase(data.get("phase", "updated"))
        return UiPathRuntimeStateEvent(
            node_name=data["function"],
            qualified_node_name=_format_location(data["file"], data["line"]),
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
                metadata={"function_start_line": data["function_start_line"]},
            )

        # Terminal events, release the controller.
        self._controller = None

        if event_type == "completed":
            # data is already a UiPathRuntimeResult from delegate.execute().
            return data

        # "error", re-raise so UiPathDebugRuntime can emit_execution_error().
        raise data
