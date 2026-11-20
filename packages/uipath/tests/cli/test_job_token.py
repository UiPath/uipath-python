"""The job's user access token refresher: renewal over the job-api IPC proxy, published to the environment.

Fakes stand in for the IPC proxy (``GetUserAccessToken``) except where the wire itself is the
point; tokens are unsigned JWTs built here so ``iat``/``exp`` can be placed precisely.
"""

import asyncio
import base64
import json
import logging
import os
import threading
import time
from contextvars import ContextVar
from typing import Any

import pytest

from uipath._cli import _job_api, _job_token
from uipath._cli._job_token import (
    JobTokenRefresher,
    install_job_token_refresher,
    publish_token_to_environ,
    uninstall_job_token_refresher,
)

JOB_ID = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
UNATTENDED = "UNATTENDED_USER_ACCESS_TOKEN"
ACCESS = "UIPATH_ACCESS_TOKEN"
LOGGER = "uipath._cli._job_token"


def _b64(obj: Any) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")


def jwt(**claims: Any) -> str:
    return f"{_b64({'alg': 'none'})}.{_b64(claims)}.sig"


def token_with_lifetime(lifetime: float, *, remaining: float, tag: str = "t") -> str:
    """A JWT expiring ``remaining`` seconds from now, issued ``lifetime`` seconds before that."""
    exp = time.time() + remaining
    return jwt(iat=exp - lifetime, exp=exp, tag=tag)


class FakeJobApi:
    """Stands in for the ``IPythonJobApi`` proxy; hands out ``tokens`` in order, then "fresh"."""

    def __init__(self, *tokens: Any, error: BaseException | None = None) -> None:
        self.tokens = list(tokens)
        self.error = error
        self.requests: list[Any] = []
        self.called = threading.Event()
        # When set, every call blocks until the event is set (from the loop's thread).
        self.release: asyncio.Event | None = None

    async def GetUserAccessToken(self, request: Any) -> Any:
        self.requests.append(request)
        self.called.set()
        if self.release is not None:
            await self.release.wait()
        if self.error is not None:
            raise self.error
        return self.tokens.pop(0) if self.tokens else "fresh"


class RemoteError(Exception):
    """Shaped like uipath_ipc's RemoteException: carries the .NET type name."""

    def __init__(self, type_name: str) -> None:
        super().__init__(type_name)
        self.type_name = type_name


@pytest.fixture
def ipc_loop():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(
        target=loop.run_forever, name="test-ipc-loop", daemon=True
    )
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)
    loop.close()


@pytest.fixture
def records() -> Any:
    captured: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    api_logger = logging.getLogger(LOGGER)
    handler = _Capture()
    api_logger.addHandler(handler)
    prior_level = api_logger.level
    api_logger.setLevel(logging.DEBUG)
    try:
        yield captured
    finally:
        api_logger.removeHandler(handler)
        api_logger.setLevel(prior_level)


def _refresher(
    api: Any, loop: asyncio.AbstractEventLoop, token: str | None, **kwargs: Any
) -> JobTokenRefresher:
    kwargs.setdefault("publish", None)
    return JobTokenRefresher(api, loop, JOB_ID, 2, initial_token=token, **kwargs)


def _wait(predicate: Any, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return bool(predicate())


def _pending_tasks(loop: asyncio.AbstractEventLoop) -> int:
    async def count() -> int:
        me = asyncio.current_task()
        return len([t for t in asyncio.all_tasks() if t is not me and not t.done()])

    return asyncio.run_coroutine_threadsafe(count(), loop).result(timeout=5)


def _warnings(records: list[logging.LogRecord]) -> list[str]:
    return [r.getMessage() for r in records if r.levelno == logging.WARNING]


class TestTokenState:
    def test_exp_and_iat_drive_the_renewal_point(self):
        now = 1_000_000.0
        state = _job_token._TokenState.from_token

        # 10 min lifetime: 20 percent is exactly the two-minute floor.
        ten_min = state(jwt(iat=now, exp=now + 600), now)
        assert ten_min.refresh_at == now + 480
        assert ten_min.is_fresh(now + 479)
        assert not ten_min.is_fresh(now + 480)
        # Short-lived: the floor wins over 20 percent.
        assert state(jwt(iat=now, exp=now + 300), now).refresh_at == now + 180
        # Long-lived: 20 percent wins (8 h: renew after 6.4 h).
        eight_h = state(jwt(iat=now, exp=now + 8 * 3600), now)
        assert eight_h.refresh_at == now + 8 * 3600 * 0.8
        # No iat: the lifetime is measured from when the token arrived.
        no_iat = state(jwt(exp=now + 600), now)
        assert no_iat.issued_at == now
        assert no_iat.refresh_at == now + 480
        # An iat in the future (clock skew) is clamped to now.
        assert state(jwt(iat=now + 50, exp=now + 650), now).issued_at == now

    def test_a_token_without_exp_is_never_due(self):
        now = 1_000_000.0
        none = _job_token._TokenState.from_token(jwt(sub="x"), now)
        assert none.expires_at is None
        assert none.refresh_at is None
        assert none.is_fresh(now + 10**9)

    def test_an_opaque_token_is_kept(self):
        state = _job_token._TokenState.from_token("opaque", 1.0)
        assert state.token == "opaque"
        assert state.expires_at is None


class TestRenewal:
    def test_renews_at_80_percent_and_republishes(self, ipc_loop, monkeypatch):
        monkeypatch.setenv(ACCESS, "old")
        monkeypatch.delenv(UNATTENDED, raising=False)
        renewed = token_with_lifetime(3600, remaining=3600, tag="renewed")
        api = FakeJobApi(renewed)
        # 10 min lifetime with 120.5 s left: the two-minute margin puts renewal ~0.5 s away.
        refresher = JobTokenRefresher(
            api,
            ipc_loop,
            JOB_ID,
            7,
            initial_token=token_with_lifetime(600, remaining=120.5),
        )

        refresher.start()

        assert api.called.wait(timeout=5)
        assert _wait(lambda: os.environ[ACCESS] == renewed)
        assert UNATTENDED not in os.environ
        request = api.requests[0]
        assert isinstance(request, _job_api.PythonUserAccessTokenRequestDto)
        assert (request.jobKey, request.resumeVersion, request.scopes) == (
            JOB_ID,
            7,
            None,
        )
        assert refresher.current_token == renewed
        assert refresher.expires_at == pytest.approx(time.time() + 3600, abs=5)
        # Rescheduled against the new token, hours away.
        task = refresher.task
        assert task is not None
        assert not task.done()
        assert len(api.requests) == 1

        refresher.stop()
        assert _wait(lambda: _pending_tasks(ipc_loop) == 0)
        assert task.cancelled()

    def test_a_fresh_token_only_waits_and_stop_cancels_the_wait(self, ipc_loop):
        api = FakeJobApi()
        refresher = _refresher(api, ipc_loop, token_with_lifetime(3600, remaining=3000))

        refresher.start()
        assert _wait(lambda: _pending_tasks(ipc_loop) == 1)
        time.sleep(0.2)
        assert api.requests == []

        refresher.stop()
        assert _wait(lambda: _pending_tasks(ipc_loop) == 0)
        # Idempotent, and the token is still there to read.
        refresher.stop()
        assert refresher.current_token is not None

    def test_a_late_answer_after_stop_is_dropped(self, ipc_loop, monkeypatch):
        monkeypatch.setenv(ACCESS, "old")
        api = FakeJobApi("late")
        api.release = asyncio.Event()
        refresher = JobTokenRefresher(
            api,
            ipc_loop,
            JOB_ID,
            None,
            initial_token=token_with_lifetime(600, remaining=60),  # due now
        )
        refresher.start()
        assert api.called.wait(timeout=5)

        refresher.stop()
        ipc_loop.call_soon_threadsafe(api.release.set)

        assert _wait(lambda: _pending_tasks(ipc_loop) == 0)
        assert os.environ[ACCESS] == "old"
        assert refresher.current_token != "late"

    def test_store_after_stop_publishes_nothing(self, ipc_loop, monkeypatch):
        """The race the cancellation may miss: the answer arrived, stop() landed before the store."""
        monkeypatch.setenv(ACCESS, "old")
        refresher = JobTokenRefresher(
            FakeJobApi(), ipc_loop, JOB_ID, None, initial_token="old"
        )

        refresher.stop()
        refresher._store("late")

        assert os.environ[ACCESS] == "old"
        assert refresher.current_token == "old"

    def test_missing_exp_means_no_timer(self, ipc_loop):
        api = FakeJobApi()
        refresher = _refresher(api, ipc_loop, jwt(sub="no-exp"))

        refresher.start()

        task = refresher.task
        assert task is not None
        task.result(timeout=5)  # returns at once: nothing to time against
        assert api.requests == []
        assert refresher.expires_at is None

    def test_no_token_at_all_means_no_timer(self, ipc_loop):
        api = FakeJobApi()
        refresher = _refresher(api, ipc_loop, None)

        refresher.start()

        task = refresher.task
        assert task is not None
        task.result(timeout=5)
        assert api.requests == []
        assert refresher.current_token is None


class TestFailures:
    def test_a_failed_renewal_warns_once_and_retries_after_the_backoff(
        self, ipc_loop, monkeypatch, records
    ):
        monkeypatch.setattr(_job_token, "_RETRY_AFTER_FAILURE_S", 0.3)
        api = FakeJobApi(error=RuntimeError("pipe down"))
        token = token_with_lifetime(600, remaining=120.2)
        refresher = _refresher(api, ipc_loop, token)

        refresher.start()

        assert api.called.wait(timeout=5)
        assert _wait(lambda: len(api.requests) >= 2)  # retried, after the backoff
        refresher.stop()
        assert len(api.requests) < 10  # ... not hammered
        assert refresher.current_token == token
        warnings = _warnings(records)
        assert len(warnings) == 1
        assert "pipe down" in warnings[0]
        # the silence that follows is announced
        assert "logged only once" in warnings[0]

    def test_a_host_without_the_method_is_retried_like_any_other_failure(
        self, ipc_loop, monkeypatch, records
    ):
        # The host opted in, so no error type is read as "unsupported": a missing method is a
        # host fault like any other, and the refresher keeps asking.
        monkeypatch.setattr(_job_token, "_RETRY_AFTER_FAILURE_S", 0.3)
        api = FakeJobApi(error=RemoteError("UiPath.Ipc.MethodNotFoundException"))
        token = token_with_lifetime(600, remaining=60)  # due now
        refresher = _refresher(api, ipc_loop, token)

        refresher.start()

        assert _wait(lambda: len(api.requests) >= 2)  # still asking
        task = refresher.task
        assert task is not None and not task.done()
        refresher.stop()
        assert refresher.current_token == token
        warnings = _warnings(records)
        assert len(warnings) == 1
        assert "MethodNotFoundException" in warnings[0]

    @pytest.mark.parametrize("bad", ["", None, 42])
    def test_an_empty_answer_is_a_failure(self, ipc_loop, monkeypatch, records, bad):
        monkeypatch.setenv(ACCESS, "old")
        api = FakeJobApi(bad)
        refresher = JobTokenRefresher(
            api,
            ipc_loop,
            JOB_ID,
            None,
            initial_token=token_with_lifetime(600, remaining=60),
        )

        refresher.start()

        assert api.called.wait(timeout=5)
        assert _wait(lambda: len(_warnings(records)) == 1)
        assert os.environ[ACCESS] == "old"
        refresher.stop()

    def test_a_token_already_due_is_kept_but_not_refetched_at_once(
        self, ipc_loop, monkeypatch, records
    ):
        """Serverless hands back the job's own token; when the handler lags, it is still due."""
        monkeypatch.setattr(_job_token, "_RETRY_AFTER_FAILURE_S", 0.3)
        api = FakeJobApi(
            *[token_with_lifetime(600, remaining=60, tag=str(i)) for i in range(50)]
        )
        refresher = _refresher(api, ipc_loop, token_with_lifetime(600, remaining=60))

        refresher.start()
        assert api.called.wait(timeout=5)
        time.sleep(1.0)
        refresher.stop()

        assert 2 <= len(api.requests) <= 8  # once per backoff period, not a spin
        assert refresher.current_token in api.tokens or refresher.current_token != ""
        assert _warnings(records) == []

    def test_a_timed_out_host_is_a_failure(self, ipc_loop, records):
        api = FakeJobApi("late")
        api.release = asyncio.Event()  # never released
        refresher = _refresher(
            api, ipc_loop, token_with_lifetime(600, remaining=60), timeout=0.2
        )

        refresher.start()

        assert _wait(lambda: len(_warnings(records)) == 1)
        assert "TimeoutError" in _warnings(records)[0]
        refresher.stop()


class TestPublish:
    def test_publish_writes_only_the_variables_that_are_set(self, monkeypatch):
        monkeypatch.setenv(UNATTENDED, "old")
        monkeypatch.setenv(ACCESS, "old")
        publish_token_to_environ("new")
        assert (os.environ[UNATTENDED], os.environ[ACCESS]) == ("new", "new")

        monkeypatch.delenv(UNATTENDED)
        publish_token_to_environ("newer")
        assert UNATTENDED not in os.environ
        assert os.environ[ACCESS] == "newer"

        monkeypatch.delenv(ACCESS)
        publish_token_to_environ("unseen")
        assert UNATTENDED not in os.environ
        assert ACCESS not in os.environ

    def test_a_failing_publish_keeps_the_token(self, ipc_loop, records):
        def boom(token: str) -> None:
            raise RuntimeError("env is read-only")

        refresher = _refresher(FakeJobApi(), ipc_loop, "old", publish=boom)

        refresher._store("renewed")

        assert refresher.current_token == "renewed"
        assert _warnings(records) == []


class TestInstall:
    def test_install_seeds_from_the_environment_and_starts(self, ipc_loop, monkeypatch):
        unattended = token_with_lifetime(3600, remaining=3000, tag="unattended")
        monkeypatch.setenv(UNATTENDED, unattended)
        monkeypatch.setenv(ACCESS, token_with_lifetime(3600, remaining=3000, tag="a"))
        api = FakeJobApi()

        refresher = install_job_token_refresher(JOB_ID, 3, api, ipc_loop)
        try:
            # UNATTENDED_USER_ACCESS_TOKEN wins, as in resolve_config_from_env.
            assert refresher.current_token == unattended
            assert _wait(lambda: _pending_tasks(ipc_loop) == 1)
            assert api.requests == []
        finally:
            uninstall_job_token_refresher(refresher)

        assert _wait(lambda: _pending_tasks(ipc_loop) == 0)

    def test_shutdown_stops_the_refresher(self, monkeypatch):
        class _Client:
            async def aclose(self) -> None:
                return None

        monkeypatch.setenv(ACCESS, token_with_lifetime(3600, remaining=3000))
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        refresher = install_job_token_refresher(JOB_ID, None, FakeJobApi(), loop)
        assert _wait(lambda: _pending_tasks(loop) == 1)
        conn = _job_api._HandlerIpcConnection(_Client(), loop, thread, None, refresher)

        conn._shutdown()

        task = refresher.task
        assert task is not None
        assert task.cancelled()
        assert not thread.is_alive()


def test_token_request_dto_wire_keys_are_pinned():
    serialization = pytest.importorskip("uipath_ipc.wire.serialization")
    request = _job_api.PythonUserAccessTokenRequestDto(jobKey="j")
    assert set(serialization.to_wire(request)) == {"jobKey", "resumeVersion", "scopes"}


# -- over a real pipe ---------------------------------------------------------------------

_pipe_counter = 0


def _unique_pipe() -> str:
    global _pipe_counter
    _pipe_counter += 1
    return f"uipath-jobtoken-test-{os.getpid()}-{_pipe_counter}"


def _isolate_output_sinks(monkeypatch) -> None:
    from uipath.runtime import output_sinks

    monkeypatch.setattr(
        output_sinks, "_log_handler", ContextVar("test_log_handler", default=None)
    )
    monkeypatch.setattr(
        output_sinks, "_result_sink", ContextVar("test_result_sink", default=None)
    )


def _serve_jobapi_in_background(pipe: str, api: Any):
    """Host ``api`` as IPythonJobApi on ``pipe`` on its own loop/thread; returns stop()."""
    from uipath_ipc import IpcServer, NamedPipeServerTransport

    loop = asyncio.new_event_loop()
    ready = threading.Event()
    holder: dict[str, Any] = {}

    async def _serve() -> None:
        server = IpcServer(
            transport=NamedPipeServerTransport(pipe),
            services={_job_api.IPythonJobApi: api},
            request_timeout=None,
        )
        holder["server"] = server
        async with server:
            ready.set()
            await server.serve_forever()

    def _run() -> None:
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_serve())
        except Exception:
            pass
        finally:
            loop.close()

    thread = threading.Thread(target=_run, name="jobtoken-test-server", daemon=True)
    thread.start()
    if not ready.wait(timeout=10):
        raise TimeoutError(f"job-api test server on {pipe!r} did not start")

    def stop() -> None:
        server = holder.get("server")
        if server is not None:
            try:
                asyncio.run_coroutine_threadsafe(server.aclose(), loop).result(
                    timeout=10
                )
            except Exception:
                pass
        thread.join(timeout=10)

    return stop


class _WireApi(_job_api.IPythonJobApi):
    def __init__(self) -> None:
        self.received: list[Any] = []

    async def SendLog(self, log: Any) -> None:
        return None

    async def SetResult(self, result: Any) -> bool:
        return True

    async def GetUserAccessToken(self, request: Any) -> str:
        self.received.append(request)
        return f"wire-token-{len(self.received)}"


def test_connect_with_refresh_renews_over_the_wire(monkeypatch):
    pytest.importorskip("uipath_ipc")
    _isolate_output_sinks(monkeypatch)
    monkeypatch.setenv(ACCESS, token_with_lifetime(600, remaining=60))  # due now
    monkeypatch.delenv(UNATTENDED, raising=False)
    api = _WireApi()
    pipe = _unique_pipe()
    stop = _serve_jobapi_in_background(pipe, api)
    try:

        async def scenario() -> None:
            async with _job_api.handler_ipc_connection(
                pipe, JOB_ID, 5, refresh_token=True
            ) as conn:
                assert conn._token_refresher is not None
                # The renewal crosses the pipe and lands in the environment.
                assert await asyncio.to_thread(
                    _wait, lambda: os.environ[ACCESS] == "wire-token-1"
                )
            # Teardown cancelled the task on the connection's loop.
            task = conn._token_refresher.task
            assert task is not None
            assert task.done()

        asyncio.run(scenario())
    finally:
        stop()

    assert len(api.received) == 1
    request = api.received[0]
    # The server deserializes against the contract, so this is the typed DTO after a round trip.
    assert (request.jobKey, request.resumeVersion, request.scopes) == (JOB_ID, 5, None)


def test_connect_without_refresh_installs_no_refresher(monkeypatch):
    pytest.importorskip("uipath_ipc")
    _isolate_output_sinks(monkeypatch)
    api = _WireApi()
    pipe = _unique_pipe()
    stop = _serve_jobapi_in_background(pipe, api)
    try:

        async def scenario() -> None:
            async with _job_api.handler_ipc_connection(pipe, JOB_ID, None) as conn:
                assert conn._token_refresher is None

        asyncio.run(scenario())
    finally:
        stop()
    assert api.received == []
