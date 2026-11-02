import logging
import os

import pytest

from uipath._cli import load_environment_variables

_KEYS = ("UIPATH_JOB_KEY", "UIPATH_URL", "UIPATH_ACCESS_TOKEN", "MY_SETTING")


@pytest.fixture
def project_dir(tmp_path, monkeypatch, caplog):
    """A cwd with a .env, and an environment that is restored after the test.

    caplog's handler is attached to the module logger directly: CLI tests that
    run setup_logging() leave the ``uipath`` logger with ``propagate = False``.
    """
    monkeypatch.chdir(tmp_path)
    logger = logging.getLogger("uipath._cli")
    monkeypatch.setattr(logger, "level", logging.WARNING)
    logger.addHandler(caplog.handler)
    for key in _KEYS:
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text(
        "UIPATH_URL=https://cloud.uipath.com/dev-org/dev-tenant\n"
        "UIPATH_ACCESS_TOKEN=dev-token\n"
        "MY_SETTING=from-dotenv\n"
    )
    yield tmp_path
    logger.removeHandler(caplog.handler)


def test_local_run_dotenv_overrides_shell(project_dir, monkeypatch):
    monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/stale/stale")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "stale-token")

    load_environment_variables()

    assert os.environ["UIPATH_URL"] == "https://cloud.uipath.com/dev-org/dev-tenant"
    assert os.environ["UIPATH_ACCESS_TOKEN"] == "dev-token"
    assert os.environ["MY_SETTING"] == "from-dotenv"


def test_job_keeps_injected_identity(project_dir, monkeypatch, caplog):
    monkeypatch.setenv("UIPATH_JOB_KEY", "job-1")
    monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/job-org/job-tenant")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "job-token")

    load_environment_variables()

    assert os.environ["UIPATH_URL"] == "https://cloud.uipath.com/job-org/job-tenant"
    assert os.environ["UIPATH_ACCESS_TOKEN"] == "job-token"
    # Keys the job did not inject still come from the .env.
    assert os.environ["MY_SETTING"] == "from-dotenv"

    warnings = [r.getMessage() for r in caplog.records]
    assert len(warnings) == 1
    assert "UIPATH_ACCESS_TOKEN, UIPATH_URL" in warnings[0]
    assert "job-token" not in warnings[0]
    assert "dev-token" not in warnings[0]


def test_job_without_conflicts_does_not_warn(project_dir, monkeypatch, caplog):
    monkeypatch.setenv("UIPATH_JOB_KEY", "job-1")
    monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/dev-org/dev-tenant")

    load_environment_variables()

    assert os.environ["UIPATH_ACCESS_TOKEN"] == "dev-token"
    assert caplog.records == []


def test_job_without_dotenv(project_dir, monkeypatch, caplog):
    (project_dir / ".env").unlink()
    monkeypatch.setenv("UIPATH_JOB_KEY", "job-1")
    monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/job-org/job-tenant")

    load_environment_variables()

    assert os.environ["UIPATH_URL"] == "https://cloud.uipath.com/job-org/job-tenant"
    assert caplog.records == []
