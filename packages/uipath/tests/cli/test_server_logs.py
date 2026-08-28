"""Forwarding job logs to the caller while the job runs.

The runtime's log interceptor strips every handler but its own, so the log file it
already writes is the only supported source. These pin the tailing, the parsing of the
runtime's line format, and the ordering guarantee that matters: the last log batch is
flushed before the terminal result, because the result is what ends the job.
"""

import asyncio
import json
import os
from typing import Any

import pytest

from uipath._cli import _server_core
from uipath._cli._server_core import _ServerState, resolve_logs_file_path
from uipath._cli._server_jobs import (
    LOG_BATCH_MAX_LINES,
    JobLogTailer,
    parse_log_line,
)


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch):
    monkeypatch.setattr(_server_core, "_state", _ServerState())


class RecordingCallback:
    def __init__(self) -> None:
        self.batches: list[list[dict[str, Any]]] = []
        self.results: list[dict[str, Any]] = []
        self.order: list[str] = []

    async def post_logs(self, job_key: str, lines: list[dict[str, Any]]) -> bool:
        self.batches.append(lines)
        self.order.append("logs")
        return True

    async def post_result(self, job_key: str, payload: dict[str, Any]) -> bool:
        self.results.append(payload)
        self.order.append("result")
        return True

    @property
    def lines(self) -> list[dict[str, Any]]:
        return [line for batch in self.batches for line in batch]


# --------------------------------------------------------------------------- #
# line parsing                                                                #
# --------------------------------------------------------------------------- #


def test_parse_log_line_splits_the_runtime_format():
    parsed = parse_log_line("[2026-07-29 17:04:19,123][INFO] hello world")

    assert parsed == {
        "timestamp": "2026-07-29 17:04:19,123",
        "level": "INFO",
        "message": "hello world",
    }


def test_parse_log_line_passes_through_an_unstructured_line():
    """Tracebacks and bare prints have no prefix; they must survive verbatim."""
    parsed = parse_log_line('  File "agent.py", line 3, in main')

    assert parsed["timestamp"] is None
    assert parsed["level"] is None
    assert parsed["message"] == '  File "agent.py", line 3, in main'


def test_parse_log_line_keeps_brackets_inside_the_message():
    parsed = parse_log_line("[2026-07-29 17:04:19,123][ERROR] failed [attempt 2]")

    assert parsed["level"] == "ERROR"
    assert parsed["message"] == "failed [attempt 2]"


# --------------------------------------------------------------------------- #
# path resolution                                                             #
# --------------------------------------------------------------------------- #


def test_resolve_logs_file_path_is_pure_wrt_process_state(tmp_path):
    """The tailer needs the path before the job applies its env, so this must not
    depend on os.environ or the cwd."""
    config = tmp_path / "uipath.json"
    config.write_text(
        json.dumps({"runtime": {"dir": "__uipath", "logsFile": "execution.log"}}),
        encoding="utf-8",
    )

    resolved = resolve_logs_file_path(
        {"UIPATH_CONFIG_PATH": "uipath.json"}, str(tmp_path)
    )

    assert resolved == os.path.abspath(str(tmp_path / "__uipath" / "execution.log"))


def test_resolve_logs_file_path_handles_an_absolute_runtime_dir(tmp_path):
    runtime_dir = tmp_path / "elsewhere"
    config = tmp_path / "uipath.json"
    config.write_text(
        json.dumps({"runtime": {"dir": str(runtime_dir), "logsFile": "execution.log"}}),
        encoding="utf-8",
    )

    resolved = resolve_logs_file_path(
        {"UIPATH_CONFIG_PATH": str(config)}, str(tmp_path)
    )

    assert resolved == os.path.abspath(str(runtime_dir / "execution.log"))


def test_resolve_logs_file_path_falls_back_to_the_default_without_a_config(tmp_path):
    """Must never return None: the caller has already stopped tailing the file itself,
    so a job with an unreadable config would otherwise produce no logs anywhere."""
    resolved = resolve_logs_file_path({}, str(tmp_path))

    assert resolved == os.path.abspath(str(tmp_path / "__uipath" / "execution.log"))


# --------------------------------------------------------------------------- #
# tailing                                                                     #
# --------------------------------------------------------------------------- #


async def test_tailer_forwards_lines_written_while_running(tmp_path):
    log_file = tmp_path / "execution.log"
    log_file.write_text("[2026-07-29 17:00:00,000][INFO] first\n", encoding="utf-8")

    callback = RecordingCallback()
    tailer = JobLogTailer("job-1", str(log_file), callback)
    task = asyncio.create_task(tailer.run())

    await asyncio.sleep(0.4)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write("[2026-07-29 17:00:01,000][ERROR] second\n")
    await asyncio.sleep(0.4)

    tailer.stop()
    await asyncio.wait_for(task, timeout=5)

    messages = [line["message"] for line in callback.lines]
    assert messages == ["first", "second"]


async def test_tailer_never_replays_a_line(tmp_path):
    log_file = tmp_path / "execution.log"
    log_file.write_text("[2026-07-29 17:00:00,000][INFO] once\n", encoding="utf-8")

    callback = RecordingCallback()
    tailer = JobLogTailer("job-1", str(log_file), callback)
    task = asyncio.create_task(tailer.run())

    await asyncio.sleep(0.8)  # several poll cycles over an unchanged file
    tailer.stop()
    await asyncio.wait_for(task, timeout=5)

    assert [line["message"] for line in callback.lines] == ["once"]


async def test_tailer_drains_what_was_written_after_stop_was_requested(tmp_path):
    """The last lines a job writes land after it finishes; they must not be lost."""
    log_file = tmp_path / "execution.log"
    log_file.write_text("", encoding="utf-8")

    callback = RecordingCallback()
    tailer = JobLogTailer("job-1", str(log_file), callback)
    task = asyncio.create_task(tailer.run())
    await asyncio.sleep(0.1)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write("[2026-07-29 17:00:02,000][INFO] final\n")
    tailer.stop()

    await asyncio.wait_for(task, timeout=5)

    assert [line["message"] for line in callback.lines] == ["final"]


async def test_tailer_batches_long_output(tmp_path):
    log_file = tmp_path / "execution.log"
    total = LOG_BATCH_MAX_LINES + 25
    log_file.write_text(
        "".join(f"[2026-07-29 17:00:00,000][INFO] line-{i}\n" for i in range(total)),
        encoding="utf-8",
    )

    callback = RecordingCallback()
    tailer = JobLogTailer("job-1", str(log_file), callback)
    tailer.stop()
    await asyncio.wait_for(tailer.run(), timeout=5)

    assert len(callback.batches) >= 2
    assert len(callback.batches[0]) == LOG_BATCH_MAX_LINES
    assert len(callback.lines) == total


async def test_logs_are_flushed_before_the_terminal_result(tmp_path):
    """The result is what ends the job on the caller's side. Any log line pushed after
    it is dropped by design, so the last batch MUST precede it."""
    import click

    from uipath._cli._server_jobs import JobRegistry

    runtime_dir = tmp_path / "__uipath"
    runtime_dir.mkdir()
    (tmp_path / "uipath.json").write_text(
        json.dumps({"runtime": {"dir": "__uipath", "logsFile": "execution.log"}}),
        encoding="utf-8",
    )

    log_path = runtime_dir / "execution.log"

    @click.command()
    def _logging_command() -> None:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("[2026-07-29 17:00:00,000][INFO] from inside the job\n")

    _server_core._state.init()
    callback = RecordingCallback()
    registry = JobRegistry()

    registry.start(
        "job-1",
        _logging_command,
        [],
        {"UIPATH_CONFIG_PATH": str(tmp_path / "uipath.json")},
        str(tmp_path),
        callback,
    )

    for _ in range(200):
        if callback.results:
            break
        await asyncio.sleep(0.05)

    assert callback.results, "job never reported a result"
    assert "logs" in callback.order, "the job's log line was never forwarded"
    assert callback.order.index("logs") < callback.order.index("result")
    assert callback.order[-1] == "result"


async def test_tailer_does_not_split_a_partially_written_line(tmp_path):
    """A logging handler writes the record and only then flushes, so a poll can catch
    half a line. Emitting the fragment produces two bogus entries that cannot be
    rejoined — the tail has to wait for its newline."""
    log_file = tmp_path / "execution.log"
    complete = b"[2026-07-29 17:00:00,000][INFO] complete" + b"\n"
    log_file.write_bytes(complete + b"[2026-07-29 17:00:01,000][INFO] half")

    callback = RecordingCallback()
    tailer = JobLogTailer("job-1", str(log_file), callback)
    task = asyncio.create_task(tailer.run())
    await asyncio.sleep(0.4)

    assert [line["message"] for line in callback.lines] == ["complete"]

    with open(log_file, "ab") as f:
        f.write(b"-and-half" + b"\n")
    await asyncio.sleep(0.4)

    tailer.stop()
    await asyncio.wait_for(task, timeout=5)

    assert [line["message"] for line in callback.lines] == ["complete", "half-and-half"]


async def test_tailer_emits_an_unterminated_final_line(tmp_path):
    """On the last drain nothing more is coming, so a trailing fragment is real output
    and must not be dropped."""
    log_file = tmp_path / "execution.log"
    log_file.write_bytes(b"no trailing newline")

    callback = RecordingCallback()
    tailer = JobLogTailer("job-1", str(log_file), callback)
    tailer.stop()

    await asyncio.wait_for(tailer.run(), timeout=5)

    assert [line["message"] for line in callback.lines] == ["no trailing newline"]


async def test_tailer_tolerates_a_missing_file(tmp_path):
    """A job that never logs must not produce an error or a stuck tailer."""
    callback = RecordingCallback()
    tailer = JobLogTailer("job-1", str(tmp_path / "never-created.log"), callback)
    tailer.stop()

    await asyncio.wait_for(tailer.run(), timeout=5)

    assert callback.batches == []
