"""Async job dispatch: enqueue a job, run it, push the outcome back to the caller.

``StartJob`` used to block for the whole job, which capped a run at the caller's
request timeout and left no channel for anything that happens *during* a job. Here
the call returns as soon as the job is registered, and the outcome travels back over
the caller-owned HTTP socket it already told us about when we ACKed readiness.

Execution is still serialised by ``_server_core``'s process-wide lock — a job mutates
process globals (logging handlers, OTel providers, env, cwd), so only one may run at a
time. Queueing changes who waits, not how many run.
"""

import asyncio
import contextlib
import enum
import os
import re
import sys
from typing import Any

from aiohttp import ClientSession, ClientTimeout, UnixConnector

from ._server_core import _run_command_isolated, resolve_logs_file_path
from ._utils._console import ConsoleLogger

console = ConsoleLogger()

# Server-side diagnostics must NOT go through ConsoleLogger while a job is running.
# ConsoleLogger resolves sys.stdout at call time, and the runtime's log interceptor has
# replaced it with a writer feeding the job's execution.log — which the tailer then reads
# and posts back. With the callback down that is a self-feeding loop: warn -> written to
# execution.log -> tailed -> posted -> fails -> warn. Bind the real stream once, before
# any job can redirect it.
_SERVER_STDERR = sys.stderr


def _server_log(message: str) -> None:
    """Diagnostics that must never be captured as a job's own logs."""
    try:
        print(message, file=_SERVER_STDERR, flush=True)
    except Exception:
        pass


CONTRACT_VERSION = 1

# A lost terminal push strands the job: StartJob no longer blocks, so no request timeout
# will complete it and nothing else on the caller's side is watching. The realistic cause
# is the callback socket being briefly unavailable (handler restart), so retry over
# minutes rather than seconds — roughly 4.5 min of wall clock across these attempts.
RESULT_PUSH_ATTEMPTS = 8
RESULT_PUSH_BACKOFF_SECONDS = 2.0
RESULT_PUSH_BACKOFF_CAP_SECONDS = 60.0
CALLBACK_TIMEOUT_SECONDS = 30

# Exit code used when the caller's callback socket is unreachable. Deliberately NOT 137:
# the caller skips result processing entirely on SIGKILL, which would throw away the very
# files we are exiting in order to let it read.
EXIT_CALLBACK_UNREACHABLE = 70

_shutdown_event: asyncio.Event | None = None
_shutdown_loop: asyncio.AbstractEventLoop | None = None


def shutdown_event() -> asyncio.Event:
    """Set when the server must stop because it can no longer reach the caller.

    Rebound whenever the running loop changes. The server has exactly one loop for its
    whole life, so in production this is created once; the rebinding keeps the flag from
    leaking between the short-lived loops that tests create.
    """
    global _shutdown_event, _shutdown_loop
    loop = asyncio.get_running_loop()
    if _shutdown_event is None or _shutdown_loop is not loop:
        _shutdown_event = asyncio.Event()
        _shutdown_loop = loop
    return _shutdown_event


def request_shutdown(reason: str) -> None:
    _server_log(f"Requesting server shutdown: {reason}")
    shutdown_event().set()


class _PostOutcome(enum.Enum):
    """Why a callback POST ended, because the three cases need different handling."""

    DELIVERED = "delivered"
    REJECTED = "rejected"  # 4xx — the caller is up and has moved on; do not retry
    UNREACHABLE = "unreachable"  # transport failure or 5xx — worth retrying


class HandlerCallback:
    """Posts job lifecycle events to the caller's Unix-socket HTTP API."""

    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path

    async def _post(self, path: str, payload: dict[str, Any]) -> _PostOutcome:
        conn = UnixConnector(path=self.socket_path)
        try:
            async with ClientSession(
                connector=conn, timeout=ClientTimeout(total=CALLBACK_TIMEOUT_SECONDS)
            ) as session:
                async with session.post(
                    f"http://localhost{path}", json=payload
                ) as response:
                    if response.status < 300:
                        return _PostOutcome.DELIVERED
                    body = await response.text()
                    _server_log(
                        f"Callback {path} rejected with {response.status}: {body}"
                    )
                    # 4xx is the caller telling us this job is unknown or already
                    # finished. Retrying cannot change that, and treating it as a lost
                    # push would take the whole server down over one stale report.
                    if 400 <= response.status < 500:
                        return _PostOutcome.REJECTED
                    return _PostOutcome.UNREACHABLE
        except Exception as e:
            _server_log(f"Callback {path} failed: {e}")
            return _PostOutcome.UNREACHABLE

    async def post_result(self, job_key: str, payload: dict[str, Any]) -> bool:
        path = f"/api/python/jobs/{job_key}/result"
        for attempt in range(1, RESULT_PUSH_ATTEMPTS + 1):
            outcome = await self._post(path, payload)
            if outcome is _PostOutcome.DELIVERED:
                return True
            if outcome is _PostOutcome.REJECTED:
                # Refused, not lost: the caller is reachable and has moved on. Report
                # success so no one tries to recover a job that is already resolved.
                return True
            if attempt < RESULT_PUSH_ATTEMPTS:
                await asyncio.sleep(
                    min(
                        RESULT_PUSH_BACKOFF_SECONDS * (2 ** (attempt - 1)),
                        RESULT_PUSH_BACKOFF_CAP_SECONDS,
                    )
                )
        # Deliberately warning, not error: ConsoleLogger.error is NoReturn (it calls
        # ctx.exit), which would raise outside a click context and kill this task.
        _server_log(
            f"Giving up on the result push for job {job_key} after "
            f"{RESULT_PUSH_ATTEMPTS} attempts; the caller will fall back to the file."
        )
        return False

    async def post_logs(self, job_key: str, lines: list[dict[str, Any]]) -> bool:
        # Logs are best-effort: a dropped batch must never delay or fail the job.
        outcome = await self._post(
            f"/api/python/jobs/{job_key}/logs",
            {"contractVersion": CONTRACT_VERSION, "jobKey": job_key, "lines": lines},
        )
        return outcome is _PostOutcome.DELIVERED


def build_result_payload(job_key: str, outcome: dict[str, Any]) -> dict[str, Any]:
    """Shape ``_run_command_isolated``'s outcome into the terminal result push."""
    return {
        "contractVersion": CONTRACT_VERSION,
        "jobKey": job_key,
        "exitCode": outcome.get("ExitCode", 1),
        "error": outcome.get("Error"),
        "unexpected": bool(outcome.get("Unexpected")),
        # state.db is never carried: agent code opens that path directly.
        "stateConveyance": "file",
        "jobConveyance": outcome.get("DocumentConveyance", "file"),
        "job": outcome.get("Document"),
    }


LOG_POLL_SECONDS = 0.25
LOG_BATCH_MAX_LINES = 200
LOG_FLUSH_TIMEOUT_SECONDS = 10
# ``[2026-07-29 17:04:19,123][INFO] message`` — the format the runtime's file handler
# emits and that the .NET FileLogsWatcher has always parsed.
LOG_LINE_RE = re.compile(
    r"^\[(?P<timestamp>[^\]]+)\]\[(?P<level>\w+)\] (?P<message>.*)$"
)


def parse_log_line(line: str) -> dict[str, Any]:
    match = LOG_LINE_RE.match(line)
    if not match:
        return {"timestamp": None, "level": None, "message": line}
    return {
        "timestamp": match.group("timestamp"),
        "level": match.group("level"),
        "message": match.group("message"),
    }


class JobLogTailer:
    """Follows the job's log file and pushes batches to the caller.

    The runtime's log interceptor strips every handler but its own, so there is no
    supported seam to attach a second one — and ``uipath-runtime`` ships on its own
    release train. Tailing the file it already writes keeps this additive: the file is
    still produced exactly as before, we just also forward it.
    """

    def __init__(self, job_key: str, path: str, callback: "HandlerCallback") -> None:
        self.job_key = job_key
        self.path = path
        self.callback = callback
        self._offset = 0
        self._stop = asyncio.Event()

    async def run(self) -> None:
        try:
            while not self._stop.is_set():
                await self._drain()
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=LOG_POLL_SECONDS)
                except asyncio.TimeoutError:
                    pass
            # The job has finished; pick up whatever it wrote on the way out, including
            # any unterminated final line.
            await self._drain(final=True)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # logs must never take the job down with them
            _server_log(f"Log tailing stopped for job {self.job_key}: {e}")

    def stop(self) -> None:
        self._stop.set()

    async def _drain(self, final: bool = False) -> None:
        try:
            if not os.path.exists(self.path):
                return
            # Binary with explicit offsets: a text-mode tell() cookie is opaque, and we
            # need to rewind past an unterminated tail.
            with open(self.path, "rb") as f:
                f.seek(self._offset)
                chunk = f.read()
        except OSError:
            return

        if not chunk:
            return

        # A logging handler writes the record and only then flushes, so the tail can be
        # half a line. Leave it for the next poll rather than reporting a fragment as a
        # complete entry — except on the final drain, where nothing more is coming.
        if not final and not chunk.endswith(b"\n"):
            cut = chunk.rfind(b"\n")
            if cut == -1:
                return
            chunk = chunk[: cut + 1]

        self._offset += len(chunk)

        batch: list[dict[str, Any]] = []
        for raw in chunk.decode("utf-8", errors="replace").splitlines():
            line = raw.rstrip("\r")
            if not line:
                continue
            batch.append(parse_log_line(line))
            if len(batch) >= LOG_BATCH_MAX_LINES:
                await self.callback.post_logs(self.job_key, batch)
                batch = []

        if batch:
            await self.callback.post_logs(self.job_key, batch)


async def _stop_tailer(
    tailer: JobLogTailer | None, task: "asyncio.Task[None] | None"
) -> None:
    """Let the tailer drain what the job just wrote, then make sure it is gone."""
    if task is None:
        return
    if tailer is not None:
        tailer.stop()
    try:
        # Shielded so a cancellation of the job task still allows the final drain.
        await asyncio.wait_for(asyncio.shield(task), LOG_FLUSH_TIMEOUT_SECONDS)
    except asyncio.CancelledError:
        # Aimed at US, not the tailer. Tidy up, then let it propagate — swallowing it
        # would carry on into the multi-minute result retry and ignore the shutdown.
        task.cancel()
        with contextlib.suppress(BaseException):
            await task
        raise
    except (asyncio.TimeoutError, Exception):
        task.cancel()
        with contextlib.suppress(BaseException):
            await task


class JobRegistry:
    """Tracks in-flight jobs so they can be deduplicated and cancelled."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def is_active(self, job_key: str) -> bool:
        task = self._tasks.get(job_key)
        return task is not None and not task.done()

    def start(
        self,
        job_key: str,
        cmd: Any,
        args: list[str],
        env_vars: dict[str, str],
        working_dir: str | None,
        callback: HandlerCallback,
    ) -> bool:
        """Register and schedule a job. False if one is already in flight for this key."""
        if self.is_active(job_key):
            return False

        task = asyncio.create_task(
            self._run(job_key, cmd, args, env_vars, working_dir, callback)
        )
        self._tasks[job_key] = task
        task.add_done_callback(lambda _: self._forget(job_key))
        return True

    def _forget(self, job_key: str) -> None:
        self._tasks.pop(job_key, None)

    async def _run(
        self,
        job_key: str,
        cmd: Any,
        args: list[str],
        env_vars: dict[str, str],
        working_dir: str | None,
        callback: HandlerCallback,
    ) -> None:
        tailer: JobLogTailer | None = None
        tail_task: "asyncio.Task[None] | None" = None

        async def finish(outcome: dict[str, Any]) -> None:
            # Flush logs BEFORE the terminal result: the result is what completes the
            # job on the caller's side, and a log line arriving after that has nowhere
            # left to go.
            await _stop_tailer(tailer, tail_task)
            delivered = await callback.post_result(
                job_key, build_result_payload(job_key, outcome)
            )
            if not delivered:
                # StartJob no longer blocks, so nothing on the caller's side will ever
                # time this job out — it would hang forever, and so would every other
                # job we are holding, since none of them can be reported either.
                # Exiting hands them all to the caller's service-exit path, which
                # completes them from the result files the runtime already wrote.
                request_shutdown(f"result callback unreachable for job {job_key}")

        try:
            # Inside the try: anything that throws here must still produce a terminal
            # report, or the caller waits forever on a job it believes was accepted.
            logs_path = resolve_logs_file_path(env_vars, working_dir)
            if logs_path:
                tailer = JobLogTailer(job_key, logs_path, callback)
                tail_task = asyncio.create_task(tailer.run())

            outcome = await _run_command_isolated(
                cmd,
                args,
                env_vars,
                working_dir,
            )
        except asyncio.CancelledError:
            # Cancelled before it took the lock — report it rather than going silent,
            # otherwise the caller waits forever for a job that will never run.
            await finish({"ExitCode": 1, "Error": "Job cancelled before execution"})
            raise
        except Exception as e:
            await finish({"ExitCode": 1, "Error": str(e), "Unexpected": True})
            return

        await finish(outcome)

    async def stop(self, job_key: str) -> bool:
        """Cancel a job that has not started executing yet.

        Once the job is running its body is on a thread via ``asyncio.to_thread``, which
        cannot be cancelled — so this only removes work that is still queued. Actually
        interrupting a running job is a separate change.
        """
        task = self._tasks.get(job_key)
        if task is None or task.done():
            return True

        task.cancel()
        return True


_registry = JobRegistry()


def get_registry() -> JobRegistry:
    return _registry
