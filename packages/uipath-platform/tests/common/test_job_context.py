import pytest

from uipath.platform.common._job_context import header_job_key
from uipath.platform.common.constants import ENV_JOB_KEY, HEADER_JOB_KEY


def test_returns_header_when_env_var_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_JOB_KEY, "test-job-key")

    assert header_job_key() == {HEADER_JOB_KEY: "test-job-key"}


def test_returns_empty_when_env_var_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_JOB_KEY, raising=False)

    assert header_job_key() == {}


def test_returns_empty_when_env_var_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_JOB_KEY, "")

    assert header_job_key() == {}
