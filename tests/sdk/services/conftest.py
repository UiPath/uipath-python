import importlib
from pathlib import Path

import pytest

from uipath.platform import UiPathApiConfig, UiPathExecutionContext


@pytest.fixture
def base_url() -> str:
    return "https://test.uipath.com"


@pytest.fixture
def org() -> str:
    return "/org"


@pytest.fixture
def tenant() -> str:
    return "/tenant"


@pytest.fixture
def secret() -> str:
    return "secret"


@pytest.fixture
def config(base_url: str, org: str, tenant: str, secret: str) -> UiPathApiConfig:
    return UiPathApiConfig(base_url=f"{base_url}{org}{tenant}", secret=secret)


@pytest.fixture
def version(monkeypatch: pytest.MonkeyPatch) -> str:
    test_version = "1.0.0"
    monkeypatch.setattr(importlib.metadata, "version", lambda _: test_version)
    return test_version


@pytest.fixture
def execution_context(monkeypatch: pytest.MonkeyPatch) -> UiPathExecutionContext:
    monkeypatch.setenv("UIPATH_ROBOT_KEY", "test-robot-key")
    return UiPathExecutionContext()


@pytest.fixture
def tests_data_path() -> Path:
    return Path(__file__).resolve().parent / "tests_data"


@pytest.fixture
def jobs_service(config, execution_context):
    from uipath.platform.orchestrator import JobsService

    return JobsService(config, execution_context)
