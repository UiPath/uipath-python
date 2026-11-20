"""Renew the job's user access token over the job-api IPC channel.

The executor hands the token to the process once, as an environment variable, and a job that
outlives it starts failing with 401. ``JobTokenRefresher`` asks the host for a new token
(``IPythonJobApi.GetUserAccessToken``) shortly before the current one expires and writes it back
to the token environment variables. ``UiPath()`` clients built from the environment re-read those
on every request (see ``uipath.platform``), so they pick the new token up without a change of
their own, and so does user code that reads the variables itself.

The host opts in (``uipath run --handler-ipc-token-refresh``, or ``refreshAccessTokenOverIpc`` on
a pooled run request); a host without the method is never asked.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

from uipath._utils._auth import parse_access_token
from uipath.platform.constants import (
    ENV_UIPATH_ACCESS_TOKEN,
    ENV_UNATTENDED_USER_ACCESS_TOKEN,
)

from ._job_api import PythonUserAccessTokenRequestDto

logger = logging.getLogger(__name__)

# A healthy host answers in well under a second (serverless hands back the job's own token, the
# Robot asks Orchestrator).
_TOKEN_REQUEST_TIMEOUT_S = 30.0
# Renew when this share of the lifetime is left (so at 80 percent of it), and never later than
# this many seconds before expiry.
_REFRESH_MARGIN_FRACTION = 0.2
_MIN_REFRESH_MARGIN_S = 120.0
# After a failed renewal, or one that returned a token already due, leave the host alone for
# this long before asking again.
_RETRY_AFTER_FAILURE_S = 30.0
_TOKEN_ENV_VARS = (ENV_UNATTENDED_USER_ACCESS_TOKEN, ENV_UIPATH_ACCESS_TOKEN)


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
    return float(value)


@dataclass(frozen=True)
class _TokenState:
    """A token with the moments that drive its renewal (epoch seconds)."""

    token: str
    issued_at: float
    expires_at: float | None

    @classmethod
    def from_token(cls, token: str, now: float) -> _TokenState:
        """Read ``iat``/``exp`` from the JWT; a token without ``exp`` is never renewed early."""
        claims = _claims(token)
        issued_at = _claim_seconds(claims, "iat")
        return cls(
            token=token,
            issued_at=now if issued_at is None else min(issued_at, now),
            expires_at=_claim_seconds(claims, "exp"),
        )

    @property
    def refresh_at(self) -> float | None:
        """When to renew: 80 percent into the lifetime, at least two minutes before expiry."""
        if self.expires_at is None:
            return None
        lifetime = max(self.expires_at - self.issued_at, 0.0)
        margin = max(_MIN_REFRESH_MARGIN_S, _REFRESH_MARGIN_FRACTION * lifetime)
        return self.expires_at - margin

    def is_fresh(self, now: float) -> bool:
        refresh_at = self.refresh_at
        return refresh_at is None or now < refresh_at


def publish_token_to_environ(token: str) -> None:
    """Republish a token under whichever token variables the process environment has set."""
    for name in _TOKEN_ENV_VARS:
        if name in os.environ:
            os.environ[name] = token


class JobTokenRefresher:
    """Renews the job's user access token on the IPC loop and publishes it to the environment.

    One task, started by :meth:`start`, sleeps until 80 percent of the current token's lifetime
    has passed (at least two minutes before expiry), asks the host, stores and publishes the
    answer, and reschedules from the new token. The host opted in, so every failure is handled
    the same way, whatever its type: the current token is kept and the host is asked again after
    30 seconds. Only the first failure is logged, as a warning that says no more will follow.
    :meth:`stop` cancels the task, a request in flight included, and a stopped refresher never
    writes to the environment again.
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
    ) -> None:
        self._proxy = proxy
        self._loop = loop
        self._job_key = job_key
        self._resume_version = resume_version
        self._timeout = timeout
        self._publish = publish
        self._clock = clock
        self._lock = threading.Lock()
        self._state: _TokenState | None = (
            _TokenState.from_token(initial_token, clock()) if initial_token else None
        )
        self._task: Future[None] | None = None
        self._retry_not_before = 0.0
        self._stopped = False
        self._reported_failure = False

    def start(self) -> None:
        """Schedule the renewal task on the IPC loop (once)."""
        if self._task is None and not self._stopped:
            self._task = asyncio.run_coroutine_threadsafe(self._run(), self._loop)

    def stop(self) -> None:
        """Cancel the renewal task; nothing is published to the environment after this."""
        with self._lock:
            self._stopped = True
        task = self._task
        if task is not None:
            task.cancel()

    @property
    def task(self) -> Future[None] | None:
        """The renewal task's handle, for callers that need to await its end."""
        return self._task

    @property
    def current_token(self) -> str | None:
        """The token last seeded or renewed, or None."""
        state = self._state
        return None if state is None else state.token

    @property
    def expires_at(self) -> float | None:
        """The current token's ``exp`` (epoch seconds), or None when unknown."""
        state = self._state
        return None if state is None else state.expires_at

    async def _run(self) -> None:
        while not self._stopped:
            state = self._state
            if state is None or state.refresh_at is None:
                return  # no token, or one without exp: nothing to time against
            now = self._clock()
            due_at = max(state.refresh_at, self._retry_not_before)
            if now < due_at:
                await asyncio.sleep(due_at - now)
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
            self._note_failure(e)
            return
        self._store(token)

    def _store(self, token: str) -> None:
        now = self._clock()
        state = _TokenState.from_token(token, now)
        with self._lock:
            if self._stopped:
                return  # a late answer after teardown must not touch the environment
            self._state = state
            # A token that is already due (serverless handing back the same soon-to-expire
            # token) would otherwise make the loop spin: wait the backoff before asking again.
            self._retry_not_before = (
                0.0 if state.is_fresh(now) else now + _RETRY_AFTER_FAILURE_S
            )
            if self._publish is None:
                return
            try:
                self._publish(token)
            except Exception:
                logger.debug(
                    "Could not republish the renewed access token", exc_info=True
                )

    def _note_failure(self, error: BaseException) -> None:
        if self._stopped:
            return  # teardown cancels in-flight work; nothing worth reporting
        with self._lock:
            self._retry_not_before = self._clock() + _RETRY_AFTER_FAILURE_S
            first = not self._reported_failure
            self._reported_failure = True
        if not first:
            return  # the one warning already said that later failures are not logged
        logger.warning(
            "Could not renew the job's user access token over IPC (%r). Keeping the current "
            "token and retrying every %g seconds. This is logged only once: later failures "
            "to renew this job's token are not logged.",
            error,
            _RETRY_AFTER_FAILURE_S,
        )


def install_job_token_refresher(
    job_key: str,
    resume_version: int | None,
    proxy: Any,
    loop: asyncio.AbstractEventLoop,
) -> JobTokenRefresher:
    """Start renewing the job's token, seeded with the one in the environment.

    Pair with :func:`uninstall_job_token_refresher` when the job ends.
    """
    initial = os.environ.get(ENV_UNATTENDED_USER_ACCESS_TOKEN) or os.environ.get(
        ENV_UIPATH_ACCESS_TOKEN
    )
    refresher = JobTokenRefresher(
        proxy, loop, job_key, resume_version, initial_token=initial
    )
    refresher.start()
    return refresher


def uninstall_job_token_refresher(refresher: JobTokenRefresher) -> None:
    """Stop the renewal task."""
    refresher.stop()
