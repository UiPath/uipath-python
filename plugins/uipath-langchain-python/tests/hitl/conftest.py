import os
import tempfile
from contextlib import contextmanager
from typing import Generator

import pytest
from click.testing import CliRunner
from uipath._utils.constants import ENV_FOLDER_KEY


@pytest.fixture
def setup_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setup test environment variables."""
    mock_env_vars: dict[str, str] = {
        "UIPATH_URL": "https://cloud.uipath.com/organization/tenant",
        ENV_FOLDER_KEY: "074f79f1-c78b-4d79-ae6a-52705cf8b852",
        "UIPATH_JOB_KEY": "91b4f03d-409e-4ff3-b0b5-efb3fd795929",
        "UIPATH_TRACING_ENABLED": "False",
        "UIPATH_ACCESS_TOKEN": "<KEY>",
        "UIPATH_TENANT_ID": "6d792d62-df81-4311-a811-389a4ba9d068",
        "UIPATH_ORGANIZATION_ID": "c1c0babe-01bc-4ed0-8adb-dc42356b10da",
    }
    for key, value in mock_env_vars.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


def get_file_path(file_name: str) -> str:
    """
    Get the path to a mock file, checking multiple possible locations.

    Args:
        file_name: Name of the file to locate

    Returns:
        Absolute path to the file
    """
    if os.path.isfile(f"mocks/{file_name}"):
        return os.path.abspath(f"mocks/{file_name}")
    else:
        return os.path.abspath(f"tests/hitl/mocks/{file_name}")


@contextmanager
def uipath_tracing_mock(httpx_mock):
    httpx_mock.add_response(
        url="https://cloud.uipath.com/organization/tenant/llmopstenant_/api/Traces/spans?traceId=None&source=Robots",
    )

    try:
        yield
    finally:
        pass
