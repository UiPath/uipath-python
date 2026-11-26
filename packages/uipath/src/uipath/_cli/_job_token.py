"""Renew a job's user access token before it expires."""

from __future__ import annotations

import asyncio
import functools
import logging
import math
import os
import threading
import time
from collections.abc import Awaitable, Callable, Iterable
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

from uipath._utils._auth import parse_access_token
from uipath.platform.common._token_renewal import set_token_renewal_running
from uipath.platform.constants import (
    ENV_UIPATH_ACCESS_TOKEN,
    ENV_UNATTENDED_USER_ACCESS_TOKEN,
)

from ._job_api import PythonUserAccessTokenRequestDto

logger = logging.getLogger(__name__)

_TOKEN_REQUEST_TIMEOUT_S = 30.0
# Renew when this share of the lifetime is left, between these many seconds before expiry.
_REFRESH_MARGIN_FRACTION = 0.2
_MIN_REFRESH_MARGIN_S = 120.0
_MAX_REFRESH_MARGIN_S = 420.0
_RETRY_AFTER_FAILURE_S = 30.0
# Longest single wait, so a suspended machine or a clock change cannot delay a renewal for long.
_MAX_SLEEP_S = 60.0
_TOKEN_ENV_VARS = (ENV_UNATTENDED_USER_ACCESS_TOKEN, ENV_UIPATH_ACCESS_TOKEN)
# Errors meaning the host cannot renew: it predates the call or the API, or it cannot mint tokens.
_HOST_CANNOT_RENEW = frozenset(
    {
        "UiPath.Ipc.MethodNotFoundException",
        "UiPath.Ipc.EndpointNotFoundException",
        "System.NotSupportedException",
    }
)


def _claims(token: str) -> dict[str, Any]:
    try:
        claims = parse_access_token(token)
    except Exception:
        return {}
    return claims if isinstance(claims, dict) else {}


def _claim_seconds(claims: dict[str, Any], name: str) -> float | None:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        seconds = float(value)
    except OverflowError:
        return None
    # NaN or infinity would break the schedule.
    return seconds if math.isfinite(seconds) else None


@dataclass(frozen=True)
class _TokenState:
    """A token and its renewal times (epoch seconds)."""

    token: str
    issued_at: float
    expires_at: float | None

    @classmethod
    def from_token(cls, token: str, now: float) -> _TokenState:
        """Read ``iat`` and ``exp`` from the JWT."""
        claims = _claims(token)
        issued_at = _claim_seconds(claims, "iat")
        return cls(
            token=token,
            issued_at=now if issued_at is None else min(issued_at, now),
            expires_at=_claim_seconds(claims, "exp"),
        )

    @property
    def refresh_at(self) -> float | None:
        """When to renew, or None for a token without ``exp``."""
        if self.expires_at is None:
            return None
        lifetime = max(self.expires_at - self.issued_at, 0.0)
        margin = min(
            _MAX_REFRESH_MARGIN_S,
            max(_MIN_REFRESH_MARGIN_S, _REFRESH_MARGIN_FRACTION * lifetime),
        )
        return self.expires_at - margin

    def is_fresh(self, now: float) -> bool:
        refresh_at = self.refresh_at
        return refresh_at is None or now < refresh_at

    def is_expired(self, now: float) -> bool:
        return self.expires_at is not None and now >= self.expires_at


def publish_token_to_environ(
    token: str, names: Iterable[str] = _TOKEN_ENV_VARS
) -> None:
    """Write the token to those of ``names`` that are set in the environment."""
    for name in names:
        if name in os.environ:
            os.environ[name] = token


class JobTokenRefresher:
    """Renews the job's user access token and publishes it to the environment.

    A failure keeps the current token and is retried. Only the first failure is logged,
    until a renewal succeeds again. A host that cannot renew, or that answers with an
    expired token, ends the renewal for the job.
    """

    def __init__(
        self,
        proxy: Any,
        loop: asyncio.AbstractEventLoop,
        job_key: str,
        resume_version: int | None,
        *,
        initial_token: str | None = None,
        timeout: float = _TOKEN_REQUEST_TIMEOUT_S,
        publish: Callable[[str], None] | None = publish_token_to_environ,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._proxy = proxy
        self._loop = loop
        self._job_key = job_key
        self._resume_version = resume_version
        self._timeout = timeout
        self._publish = publish
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._state: _TokenState | None = (
            _TokenState.from_token(initial_token, clock()) if initial_token else None
        )
        self._task: Future[None] | None = None
        self._retry_not_before = 0.0
        self._stopped = False
        self._reported_failure = False
        # Whether this refresher counts as a running renewal (see start and stop).
        self._counted = False

    def start(self) -> None:
        """Start renewing (once)."""
        if self._task is None and not self._stopped:
            self._counted = True
            set_token_renewal_running(True)
            self._task = asyncio.run_coroutine_threadsafe(self._run(), self._loop)

    def stop(self) -> None:
        """Stop renewing; nothing is published after this."""
        with self._lock:
            self._stopped = True
            counted, self._counted = self._counted, False
        if counted:
            set_token_renewal_running(False)
        task = self._task
        if task is not None:
            task.cancel()

    async def _run(self) -> None:
        while not self._stopped:
            state = self._state
            if state is None or state.refresh_at is None:
                logger.debug(
                    "Not renewing the job's user access token: there is no token with an "
                    "expiry to schedule against."
                )
                return
            now = self._clock()
            due_at = max(state.refresh_at, self._retry_not_before)
            if now < due_at:
                await self._sleep(min(due_at - now, _MAX_SLEEP_S))
                continue
            await self._refresh_once()

    async def _refresh_once(self) -> None:
        request = PythonUserAccessTokenRequestDto(
            jobKey=self._job_key, resumeVersion=self._resume_version, scopes=None
        )
        try:
            token = await asyncio.wait_for(
                self._proxy.GetUserAccessToken(request), timeout=self._timeout
            )
            if not isinstance(token, str) or not token:
                raise RuntimeError(f"the host returned no token ({token!r})")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            if getattr(e, "type_name", None) in _HOST_CANNOT_RENEW:
                self._host_cannot_renew(e)
            else:
                self._note_failure(e)
            return
        self._store(token)

    def _store(self, token: str) -> None:
        now = self._clock()
        state = _TokenState.from_token(token, now)
        if state.is_expired(now):
            self._host_answered_expired()
            return
        with self._lock:
            if self._stopped:
                return
            self._state = state
            # An answer that is already due must not make the loop spin.
            self._retry_not_before = (
                0.0 if state.is_fresh(now) else now + _RETRY_AFTER_FAILURE_S
            )
            recovered = self._reported_failure
            self._reported_failure = False
            if self._publish is not None:
                try:
                    self._publish(token)
                except Exception:
                    logger.debug(
                        "Could not republish the renewed access token", exc_info=True
                    )
        if recovered:
            logger.info("Renewed the job's user access token after an earlier failure.")

    def _note_failure(self, error: BaseException) -> None:
        if self._stopped:
            return
        with self._lock:
            self._retry_not_before = self._clock() + _RETRY_AFTER_FAILURE_S
            first = not self._reported_failure
            self._reported_failure = True
        if not first:
            return
        logger.warning(
            "Could not renew the job's user access token over IPC (%r). Keeping the current "
            "token and retrying every %g seconds. This is logged only once: further "
            "failures are not logged until a renewal succeeds.",
            error,
            _RETRY_AFTER_FAILURE_S,
        )

    def _host_cannot_renew(self, error: BaseException) -> None:
        with self._lock:
            self._stopped = True
        logger.info(
            "Not renewing the job's user access token: the host does not offer it (%s).",
            getattr(error, "type_name", None),
        )

    def _host_answered_expired(self) -> None:
        with self._lock:
            if self._stopped:
                return
            self._stopped = True
        logger.warning(
            "Stopped renewing the job's user access token: the host answered with a token "
            "that has already expired. Calls that need the token will fail from now on."
        )


def install_job_token_refresher(
    job_key: str,
    resume_version: int | None,
    proxy: Any,
    loop: asyncio.AbstractEventLoop,
) -> JobTokenRefresher:
    """Start renewing the job's token, starting from the one in the environment."""
    initial = os.environ.get(ENV_UNATTENDED_USER_ACCESS_TOKEN) or os.environ.get(
        ENV_UIPATH_ACCESS_TOKEN
    )
    # Another token under the other variable name is left alone.
    names = tuple(
        name for name in _TOKEN_ENV_VARS if initial and os.environ.get(name) == initial
    )
    refresher = JobTokenRefresher(
        proxy,
        loop,
        job_key,
        resume_version,
        initial_token=initial,
        publish=functools.partial(publish_token_to_environ, names=names),
    )
    refresher.start()
    return refresher
