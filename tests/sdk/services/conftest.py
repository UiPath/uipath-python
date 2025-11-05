import importlib
from functools import wraps
from pathlib import Path

import pytest

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath.tracing import TracingManager


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
def config(base_url: str, org: str, tenant: str, secret: str) -> Config:
    return Config(base_url=f"{base_url}{org}{tenant}", secret=secret)


@pytest.fixture
def version(monkeypatch: pytest.MonkeyPatch) -> str:
    test_version = "1.0.0"
    monkeypatch.setattr(importlib.metadata, "version", lambda _: test_version)
    return test_version


@pytest.fixture
def execution_context(monkeypatch: pytest.MonkeyPatch) -> ExecutionContext:
    monkeypatch.setenv("UIPATH_ROBOT_KEY", "test-robot-key")
    return ExecutionContext()


@pytest.fixture
def tests_data_path() -> Path:
    return Path(__file__).resolve().parent / "tests_data"


@pytest.fixture(autouse=True)
def mock_tracer():
    def mock_tracer_impl(**kwargs):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        return decorator

    TracingManager.reapply_traced_decorator(mock_tracer_impl)
    yield
    TracingManager.reapply_traced_decorator(None)
