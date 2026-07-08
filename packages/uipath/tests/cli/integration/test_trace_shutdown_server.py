import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Generator, cast

import pytest

from tests.cli.utils.server import (
    get_free_port,
    start_cli_server_thread,
    start_job_with_env,
)


class TraceServer(ThreadingHTTPServer):
    posts: list[bytes]


class TraceHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length)
        cast(TraceServer, self.server).posts.append(body)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def trace_stub() -> Generator[tuple[TraceServer, str], None, None]:
    port = get_free_port()
    server = TraceServer(("127.0.0.1", port), TraceHandler)
    server.posts = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield server, f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        server.server_close()


def write_project(project: Path) -> None:
    (project / "entrypoint.py").write_text(
        """from dataclasses import dataclass
from uipath.tracing import traced


@dataclass
class Input:
    message: str


@dataclass
class Output:
    message: str


@traced(name="actual-agent-span")
def main(input: Input) -> Output:
    return Output(message=f"ok: {input.message}")
""",
        encoding="utf-8",
    )
    (project / "uipath.json").write_text(
        json.dumps({"agents": {"main": "entrypoint.py:main"}}, indent=2),
        encoding="utf-8",
    )


async def run_traced_job(
    port: int,
    project: Path,
    trace_url: str,
    job_key: str,
    command: str,
    extra_args: list[str],
) -> tuple[dict[str, Any], Path]:
    input_file = project / f"{job_key}-input.json"
    output_file = project / f"{job_key}-output.json"
    input_file.write_text(json.dumps({"message": job_key}), encoding="utf-8")

    response = await start_job_with_env(
        port,
        job_key,
        command,
        [
            "main",
            "--input-file",
            str(input_file),
            "--output-file",
            str(output_file),
            *extra_args,
        ],
        {
            "UIPATH_ACCESS_TOKEN": "fake-token",
            "UIPATH_JOB_KEY": job_key,
            "UIPATH_ORGANIZATION_ID": "org-123",
            "UIPATH_TENANT_ID": "tenant-123",
            "UIPATH_TRACE_BASE_URL": trace_url,
            "UIPATH_TRACING_ENABLED": "true",
            "LOG_LEVEL": "DEBUG",
        },
        working_directory=str(project),
    )
    return response, output_file


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("command", "extra_args"),
    [
        ("run", []),
        ("debug", ["--attach", "none"]),
    ],
)
def test_server_runs_two_traced_jobs_after_trace_shutdown(
    tmp_path: Path,
    trace_stub: tuple[TraceServer, str],
    command: str,
    extra_args: list[str],
) -> None:
    port = get_free_port()
    start_cli_server_thread(port)

    trace_server, trace_url = trace_stub
    project = tmp_path / "project"
    project.mkdir()
    write_project(project)

    job1_response, job1_output = asyncio.run(
        run_traced_job(port, project, trace_url, "job-1", command, extra_args)
    )
    job2_response, job2_output = asyncio.run(
        run_traced_job(port, project, trace_url, "job-2", command, extra_args)
    )

    assert job1_response["success"] is True, job1_response
    assert job2_response["success"] is True, job2_response
    assert read_json(job1_output) == {"message": "ok: job-1"}
    assert read_json(job2_output) == {"message": "ok: job-2"}

    result = read_json(project / "__uipath" / "output.json")
    assert result["status"] == "successful"
    assert "error" not in result
    assert trace_server.posts
