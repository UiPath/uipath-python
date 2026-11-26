"""Tests for the job's user access token refresher."""

import asyncio
import base64
import json
import logging
import os
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import Future
from contextvars import ContextVar
from typing import Any

import pytest

from uipath._cli import _job_api, _job_token
from uipath._cli._job_token import (
    JobTokenRefresher,
    install_job_token_refresher,
    publish_token_to_environ,
)
from uipath.platform.common._token_renewal import token_renewal_running

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
    """Fake job API proxy; hands out ``tokens`` in order, then "fresh".

    An exception among the tokens is raised instead of returned.
    """

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
        answer = self.tokens.pop(0) if self.tokens else "fresh"
        if isinstance(answer, BaseException):
            raise answer
        return answer


class RemoteError(Exception):
    """Shaped like uipath_ipc's RemoteException."""

    def __init__(self, type_name: str) -> None:
        super().__init__(type_name)
        self.type_name = type_name


@pytest.fixture
def ipc_loop() -> Iterator[asyncio.AbstractEventLoop]:
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
def records() -> Iterator[list[logging.LogRecord]]:
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


def _token(refresher: JobTokenRefresher) -> str | None:
    state = refresher._state
    return None if state is None else state.token


def _task(refresher: JobTokenRefresher) -> Future[None]:
    task = refresher._task
    assert task is not None
    return task


class VirtualTime:
    """A clock that moves only when the refresher sleeps, so timing tests need no real waits.

    A sleep that would pass ``horizon`` parks until the refresher is stopped.
    """

    def __init__(self, start: float = 1_000_000.0, horizon: float = float("inf")):
        self.now = start
        self.horizon = start + horizon
        self.sleeps: list[float] = []
        self.parked = threading.Event()

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        if self.now + seconds > self.horizon:
            self.parked.set()
            await asyncio.Event().wait()
        self.now += seconds
        await asyncio.sleep(0)

    def token(self, *, remaining: float, lifetime: float = 600, tag: str = "t") -> str:
        """A JWT expiring ``remaining`` virtual seconds from now."""
        exp = self.now + remaining
        return jwt(iat=exp - lifetime, exp=exp, tag=tag)


class TestTokenState:
    def test_exp_and_iat_drive_the_renewal_point(self) -> None:
        now = 1_000_000.0
        state = _job_token._TokenState.from_token

        # 10 min lifetime: 20 percent is exactly the two-minute floor.
        ten_min = state(jwt(iat=now, exp=now + 600), now)
        assert ten_min.refresh_at == now + 480
        assert ten_min.is_fresh(now + 479)
        assert not ten_min.is_fresh(now + 480)
        # Short-lived: the floor wins over 20 percent.
        assert state(jwt(iat=now, exp=now + 300), now).refresh_at == now + 180
        # 30 min lifetime: 20 percent (6 min) is within the bounds.
        assert state(jwt(iat=now, exp=now + 1800), now).refresh_at == now + 1440
        # 35 min lifetime: 20 percent is exactly the seven-minute cap.
        assert state(jwt(iat=now, exp=now + 2100), now).refresh_at == now + 1680
        # Long-lived: the cap wins over 20 percent (1 h: renew 7 min before expiry).
        one_h = state(jwt(iat=now, exp=now + 3600), now)
        assert one_h.refresh_at == now + 3600 - 420
        eight_h = state(jwt(iat=now, exp=now + 8 * 3600), now)
        assert eight_h.refresh_at == now + 8 * 3600 - 420
        # No iat: the lifetime is measured from when the token arrived.
        no_iat = state(jwt(exp=now + 600), now)
        assert no_iat.issued_at == now
        assert no_iat.refresh_at == now + 480
        # An iat in the future (clock skew) is clamped to now.
        assert state(jwt(iat=now + 50, exp=now + 650), now).issued_at == now

    def test_a_token_without_exp_is_never_due(self) -> None:
        now = 1_000_000.0
        none = _job_token._TokenState.from_token(jwt(sub="x"), now)
        assert none.expires_at is None
        assert none.refresh_at is None
        assert none.is_fresh(now + 10**9)
        assert not none.is_expired(now + 10**9)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), 10**400])
    def test_an_unusable_exp_or_iat_is_ignored(self, bad: float) -> None:
        now = 1_000_000.0
        state = _job_token._TokenState.from_token

        no_exp = state(jwt(iat=now, exp=bad), now)
        assert no_exp.expires_at is None
        assert no_exp.refresh_at is None
        # A bad iat counts the lifetime from now instead.
        no_iat = state(jwt(iat=bad, exp=now + 600), now)
        assert no_iat.issued_at == now
        assert no_iat.refresh_at == now + 480

    def test_a_token_is_expired_from_its_exp_on(self) -> None:
        now = 1_000_000.0
        state = _job_token._TokenState.from_token(jwt(iat=now, exp=now + 600), now)
        assert not state.is_expired(now + 599)
        assert state.is_expired(now + 600)

    def test_an_opaque_token_is_kept(self) -> None:
        state = _job_token._TokenState.from_token("opaque", 1.0)
        assert state.token == "opaque"
        assert state.expires_at is None


class TestRenewal:
    def test_renews_at_80_percent_and_republishes(
        self, ipc_loop: asyncio.AbstractEventLoop, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        assert _token(refresher) == renewed
        state = refresher._state
        assert state is not None
        assert state.expires_at == pytest.approx(time.time() + 3600, abs=5)
        # Rescheduled against the new token, hours away.
        task = _task(refresher)
        assert not task.done()
        assert len(api.requests) == 1

        refresher.stop()
        assert _wait(lambda: _pending_tasks(ipc_loop) == 0)
        assert task.cancelled()

    def test_a_fresh_token_only_waits_and_stop_cancels_the_wait(
        self, ipc_loop: asyncio.AbstractEventLoop
    ) -> None:
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
        assert _token(refresher) is not None

    def test_start_and_stop_switch_following_the_renewed_token(
        self, ipc_loop: asyncio.AbstractEventLoop
    ) -> None:
        refresher = _refresher(
            FakeJobApi(), ipc_loop, token_with_lifetime(3600, remaining=3000)
        )
        assert token_renewal_running() is False

        refresher.start()
        assert token_renewal_running() is True

        refresher.stop()
        assert token_renewal_running() is False

    def test_one_renewal_stopping_leaves_another_running(
        self, ipc_loop: asyncio.AbstractEventLoop
    ) -> None:
        token = token_with_lifetime(3600, remaining=3000)
        first = _refresher(FakeJobApi(), ipc_loop, token)
        second = _refresher(FakeJobApi(), ipc_loop, token)
        never_started = _refresher(FakeJobApi(), ipc_loop, token)

        first.start()
        second.start()
        first.stop()
        first.stop()
        never_started.stop()
        assert token_renewal_running() is True

        second.stop()
        assert token_renewal_running() is False

    def test_a_late_answer_after_stop_is_dropped(
        self, ipc_loop: asyncio.AbstractEventLoop, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        assert _token(refresher) != "late"

    def test_store_after_stop_publishes_nothing(
        self, ipc_loop: asyncio.AbstractEventLoop, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The race the cancellation may miss: the answer arrived, stop() landed before the store."""
        monkeypatch.setenv(ACCESS, "old")
        refresher = JobTokenRefresher(
            FakeJobApi(), ipc_loop, JOB_ID, None, initial_token="old"
        )

        refresher.stop()
        refresher._store("late")

        assert os.environ[ACCESS] == "old"
        assert _token(refresher) == "old"

    def test_missing_exp_means_no_timer(
        self, ipc_loop: asyncio.AbstractEventLoop, records: list[logging.LogRecord]
    ) -> None:
        api = FakeJobApi()
        refresher = _refresher(api, ipc_loop, jwt(sub="no-exp"))

        refresher.start()

        _task(refresher).result(timeout=5)  # returns at once: nothing to time against
        assert api.requests == []
        # Normal for a job without a usable token, so not a warning.
        assert _warnings(records) == []
        assert any("no token with an expiry" in r.getMessage() for r in records)

    def test_no_token_at_all_means_no_timer(
        self, ipc_loop: asyncio.AbstractEventLoop, records: list[logging.LogRecord]
    ) -> None:
        api = FakeJobApi()
        refresher = _refresher(api, ipc_loop, None)

        refresher.start()

        _task(refresher).result(timeout=5)
        assert api.requests == []
        assert _token(refresher) is None
        assert _warnings(records) == []

    def test_a_clock_jump_during_the_wait_is_noticed_within_one_slice(
        self, ipc_loop: asyncio.AbstractEventLoop, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_job_token, "_MAX_SLEEP_S", 0.1)
        jump = [0.0]
        api = FakeJobApi(token_with_lifetime(3600, remaining=3600))
        refresher = _refresher(
            api,
            ipc_loop,
            token_with_lifetime(3600, remaining=3000),  # renewal is ~43 minutes away
            clock=lambda: time.time() + jump[0],
        )

        refresher.start()
        time.sleep(0.3)
        assert api.requests == []

        jump[0] = 2700.0  # the wall clock moves past the renewal point mid-wait
        assert api.called.wait(timeout=5)
        refresher.stop()


class TestFailures:
    def test_a_failed_renewal_warns_once_and_retries_after_the_backoff(
        self,
        ipc_loop: asyncio.AbstractEventLoop,
        records: list[logging.LogRecord],
    ) -> None:
        time_ = VirtualTime(horizon=100)
        api = FakeJobApi(error=RuntimeError("pipe down"))
        token = time_.token(remaining=110)  # due now
        refresher = _refresher(
            api, ipc_loop, token, clock=time_.clock, sleep=time_.sleep
        )

        refresher.start()

        assert time_.parked.wait(timeout=5)
        refresher.stop()
        # Asked at 0, 30, 60 and 90 seconds: once per backoff period, not hammered.
        assert len(api.requests) == 4
        assert time_.sleeps == [30.0] * 4
        assert _token(refresher) == token
        warnings = _warnings(records)
        assert len(warnings) == 1
        assert "pipe down" in warnings[0]
        # the silence that follows is announced
        assert "logged only once" in warnings[0]

    @pytest.mark.parametrize(
        "type_name",
        [
            "UiPath.Ipc.MethodNotFoundException",
            "UiPath.Ipc.EndpointNotFoundException",
            "System.NotSupportedException",
        ],
    )
    def test_a_host_that_cannot_renew_ends_the_renewal_quietly(
        self,
        ipc_loop: asyncio.AbstractEventLoop,
        monkeypatch: pytest.MonkeyPatch,
        records: list[logging.LogRecord],
        type_name: str,
    ) -> None:
        monkeypatch.setattr(_job_token, "_RETRY_AFTER_FAILURE_S", 0.1)
        api = FakeJobApi(error=RemoteError(type_name))
        token = token_with_lifetime(600, remaining=60)  # due now
        refresher = _refresher(api, ipc_loop, token)

        refresher.start()

        _task(refresher).result(timeout=5)  # the loop ends by itself
        assert len(api.requests) == 1  # asked once, never again
        assert _token(refresher) == token
        assert _warnings(records) == []
        infos = [r.getMessage() for r in records if r.levelno == logging.INFO]
        assert any(type_name in m for m in infos)

    def test_any_other_remote_error_is_retried(
        self,
        ipc_loop: asyncio.AbstractEventLoop,
        monkeypatch: pytest.MonkeyPatch,
        records: list[logging.LogRecord],
    ) -> None:
        monkeypatch.setattr(_job_token, "_RETRY_AFTER_FAILURE_S", 0.3)
        api = FakeJobApi(error=RemoteError("System.NullReferenceException"))
        token = token_with_lifetime(600, remaining=60)  # due now
        refresher = _refresher(api, ipc_loop, token)

        refresher.start()

        assert _wait(lambda: len(api.requests) >= 2)  # still asking
        assert not _task(refresher).done()
        refresher.stop()
        assert _token(refresher) == token
        warnings = _warnings(records)
        assert len(warnings) == 1
        assert "NullReferenceException" in warnings[0]

    def test_a_new_failure_after_a_recovery_warns_again(
        self,
        ipc_loop: asyncio.AbstractEventLoop,
        monkeypatch: pytest.MonkeyPatch,
        records: list[logging.LogRecord],
    ) -> None:
        monkeypatch.setattr(_job_token, "_RETRY_AFTER_FAILURE_S", 0.2)
        api = FakeJobApi(
            RuntimeError("down"),
            token_with_lifetime(600, remaining=60, tag="still-due"),
            RuntimeError("down again"),
            token_with_lifetime(3600, remaining=3600, tag="fresh"),
        )
        refresher = _refresher(api, ipc_loop, token_with_lifetime(600, remaining=60))

        refresher.start()

        assert _wait(lambda: len(api.requests) == 4)
        refresher.stop()
        failures = [w for w in _warnings(records) if "Could not renew" in w]
        assert len(failures) == 2
        assert "'down'" in failures[0] and "'down again'" in failures[1]
        recoveries = [
            r for r in records if "after an earlier failure" in r.getMessage()
        ]
        assert len(recoveries) == 2

    @pytest.mark.parametrize("bad", ["", None, 42])
    def test_an_empty_answer_is_a_failure(
        self,
        ipc_loop: asyncio.AbstractEventLoop,
        monkeypatch: pytest.MonkeyPatch,
        records: list[logging.LogRecord],
        bad: Any,
    ) -> None:
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
        self,
        ipc_loop: asyncio.AbstractEventLoop,
        records: list[logging.LogRecord],
    ) -> None:
        """An answer that is already due waits the backoff instead of spinning."""
        time_ = VirtualTime(horizon=100)
        # Due as soon as they arrive, but still valid for the whole test.
        answers = [time_.token(remaining=110, tag=str(i)) for i in range(10)]
        api = FakeJobApi(*answers)
        refresher = _refresher(
            api,
            ipc_loop,
            time_.token(remaining=110),
            clock=time_.clock,
            sleep=time_.sleep,
        )

        refresher.start()
        assert time_.parked.wait(timeout=5)
        refresher.stop()

        # Asked at 0, 30, 60 and 90 seconds: once per backoff period, not a spin.
        assert len(api.requests) == 4
        assert time_.sleeps == [30.0] * 4
        # Each due answer was kept.
        assert _token(refresher) == answers[3]
        assert _warnings(records) == []

    def test_an_expired_answer_ends_the_renewal_with_one_warning(
        self,
        ipc_loop: asyncio.AbstractEventLoop,
        records: list[logging.LogRecord],
    ) -> None:
        published: list[str] = []
        api = FakeJobApi(token_with_lifetime(600, remaining=-1, tag="expired"))
        token = token_with_lifetime(600, remaining=60)  # due now
        refresher = _refresher(api, ipc_loop, token, publish=published.append)

        refresher.start()

        _task(refresher).result(timeout=5)  # the loop ends by itself
        assert len(api.requests) == 1
        assert _token(refresher) == token
        assert published == []
        warnings = _warnings(records)
        assert len(warnings) == 1
        assert "already expired" in warnings[0]

    def test_the_same_token_handed_back_until_it_expires_ends_the_renewal(
        self,
        ipc_loop: asyncio.AbstractEventLoop,
        records: list[logging.LogRecord],
    ) -> None:
        """A host that does not renew keeps answering with the token the job holds."""
        time_ = VirtualTime()
        token = time_.token(remaining=100)  # due now, expires in 100 seconds
        api = FakeJobApi(*[token] * 10)
        refresher = _refresher(
            api, ipc_loop, token, clock=time_.clock, sleep=time_.sleep
        )

        refresher.start()

        _task(refresher).result(timeout=5)  # the loop ends once the token expired
        # Asked at 0, 30, 60 and 90 seconds while it was valid, then once it had expired.
        assert len(api.requests) == 5
        assert time_.sleeps == [30.0] * 4
        warnings = _warnings(records)
        assert len(warnings) == 1
        assert "already expired" in warnings[0]

    def test_a_timed_out_host_is_a_failure(
        self, ipc_loop: asyncio.AbstractEventLoop, records: list[logging.LogRecord]
    ) -> None:
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
    def test_publish_writes_only_the_variables_that_are_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

    def test_publish_can_be_limited_to_some_variables(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(UNATTENDED, "job")
        monkeypatch.setenv(ACCESS, "mine")

        publish_token_to_environ("new", names=(UNATTENDED,))

        assert (os.environ[UNATTENDED], os.environ[ACCESS]) == ("new", "mine")

    def test_a_failing_publish_keeps_the_token(
        self, ipc_loop: asyncio.AbstractEventLoop, records: list[logging.LogRecord]
    ) -> None:
        def boom(token: str) -> None:
            raise RuntimeError("env is read-only")

        refresher = _refresher(FakeJobApi(), ipc_loop, "old", publish=boom)

        refresher._store("renewed")

        assert _token(refresher) == "renewed"
        assert _warnings(records) == []


class TestInstall:
    def test_install_seeds_from_the_environment_and_starts(
        self, ipc_loop: asyncio.AbstractEventLoop, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        unattended = token_with_lifetime(3600, remaining=3000, tag="unattended")
        monkeypatch.setenv(UNATTENDED, unattended)
        monkeypatch.setenv(ACCESS, token_with_lifetime(3600, remaining=3000, tag="a"))
        api = FakeJobApi()

        refresher = install_job_token_refresher(JOB_ID, 3, api, ipc_loop)
        try:
            # UNATTENDED_USER_ACCESS_TOKEN wins, as in resolve_config_from_env.
            assert _token(refresher) == unattended
            assert _wait(lambda: _pending_tasks(ipc_loop) == 1)
            assert api.requests == []
        finally:
            refresher.stop()

        assert _wait(lambda: _pending_tasks(ipc_loop) == 0)

    @pytest.mark.parametrize("same_token", [True, False])
    def test_install_renews_only_the_variables_that_hold_the_seed_token(
        self,
        ipc_loop: asyncio.AbstractEventLoop,
        monkeypatch: pytest.MonkeyPatch,
        same_token: bool,
    ) -> None:
        seed = token_with_lifetime(600, remaining=60)  # due now
        renewed = token_with_lifetime(3600, remaining=3600, tag="renewed")
        monkeypatch.setenv(UNATTENDED, seed)
        monkeypatch.setenv(ACCESS, seed if same_token else "someone-elses")

        refresher = install_job_token_refresher(
            JOB_ID, None, FakeJobApi(renewed), ipc_loop
        )
        try:
            assert _wait(lambda: os.environ[UNATTENDED] == renewed)
        finally:
            refresher.stop()

        assert os.environ[ACCESS] == (renewed if same_token else "someone-elses")

    def test_shutdown_stops_the_refresher(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

        assert _task(refresher).cancelled()
        assert not thread.is_alive()


def test_token_request_dto_wire_keys_are_pinned() -> None:
    serialization = pytest.importorskip("uipath_ipc.wire.serialization")
    request = _job_api.PythonUserAccessTokenRequestDto(jobKey="j")
    assert set(serialization.to_wire(request)) == {"jobKey", "resumeVersion", "scopes"}


# -- over a real pipe ---------------------------------------------------------------------

_pipe_counter = 0


def _unique_pipe() -> str:
    global _pipe_counter
    _pipe_counter += 1
    return f"uipath-jobtoken-test-{os.getpid()}-{_pipe_counter}"


def _isolate_output_sinks(monkeypatch: pytest.MonkeyPatch) -> None:
    from uipath.runtime import output_sinks

    monkeypatch.setattr(
        output_sinks, "_log_handler", ContextVar("test_log_handler", default=None)
    )
    monkeypatch.setattr(
        output_sinks, "_result_sink", ContextVar("test_result_sink", default=None)
    )


def _serve_jobapi_in_background(
    pipe: str, api: Any, contract: Any = None
) -> Callable[[], None]:
    """Host ``api`` as IPythonJobApi on ``pipe`` on its own loop/thread; returns stop()."""
    from uipath_ipc import IpcServer, NamedPipeServerTransport

    loop = asyncio.new_event_loop()
    ready = threading.Event()
    holder: dict[str, Any] = {}

    async def _serve() -> None:
        server = IpcServer(
            transport=NamedPipeServerTransport(pipe),
            services={contract or _job_api.IPythonJobApi: api},
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


def test_connecting_renews_over_the_wire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("uipath_ipc")
    _isolate_output_sinks(monkeypatch)
    monkeypatch.setenv(ACCESS, token_with_lifetime(600, remaining=60))  # due now
    monkeypatch.delenv(UNATTENDED, raising=False)
    api = _WireApi()
    pipe = _unique_pipe()
    stop = _serve_jobapi_in_background(pipe, api)
    try:

        async def scenario() -> None:
            async with _job_api.handler_ipc_connection(pipe, JOB_ID, 5) as conn:
                assert conn._token_refresher is not None
                # The renewal crosses the pipe and lands in the environment.
                assert await asyncio.to_thread(
                    _wait, lambda: os.environ[ACCESS] == "wire-token-1"
                )
                assert token_renewal_running() is True
            # Teardown stops the renewal.
            assert token_renewal_running() is False

        asyncio.run(scenario())
    finally:
        stop()

    assert len(api.received) == 1
    request = api.received[0]
    # The server deserializes against the contract, so this is the typed DTO after a round trip.
    assert (request.jobKey, request.resumeVersion, request.scopes) == (JOB_ID, 5, None)


def _old_job_api_contract() -> type:
    """IPythonJobApi as served by a host from before the token call."""
    methods = {
        name: getattr(_job_api.IPythonJobApi, name)
        for name in vars(_job_api.IPythonJobApi)
        if not name.startswith("_") and name != "GetUserAccessToken"
    }
    return type("IPythonJobApi", (), methods)


def test_a_host_without_the_method_ends_the_renewal_over_the_wire(
    monkeypatch: pytest.MonkeyPatch, records: list[logging.LogRecord]
) -> None:
    pytest.importorskip("uipath_ipc")
    _isolate_output_sinks(monkeypatch)
    monkeypatch.setenv(ACCESS, token_with_lifetime(600, remaining=60))  # due now
    monkeypatch.delenv(UNATTENDED, raising=False)
    api = _WireApi()
    pipe = _unique_pipe()
    stop = _serve_jobapi_in_background(pipe, api, contract=_old_job_api_contract())
    try:

        async def scenario() -> None:
            async with _job_api.handler_ipc_connection(pipe, JOB_ID, None) as conn:
                refresher = conn._token_refresher
                assert refresher is not None
                # The host's own error ends the renewal: no retry, no warning.
                assert await asyncio.to_thread(_wait, lambda: _task(refresher).done())

        asyncio.run(scenario())
    finally:
        stop()

    assert api.received == []
    assert _warnings(records) == []
