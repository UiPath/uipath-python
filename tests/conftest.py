import os
import tempfile
from typing import Generator

import pytest
from click.testing import CliRunner

from tests.cli.utils.project_details import ProjectDetails
from tests.cli.utils.uipath_json import UiPathJson


@pytest.fixture
def mock_env_vars() -> dict[str, str]:
    """Fixture to provide mock environment variables."""
    return {
        "UIPATH_URL": "https://cloud.uipath.com",
        "UIPATH_ACCESS_TOKEN": "mock_token",
    }


@pytest.fixture
def mock_personal_workspace_info() -> tuple[str, str]:
    """Fixture to provide mock personal workspace info."""
    return ("tenant_feed", "my-workspace-feed")


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


@pytest.fixture
def mock_project(temp_dir: str) -> str:
    """Create a mock project structure for testing."""
    # Create sample files
    with open(os.path.join(temp_dir, "main.py"), "w") as f:
        f.write("def main(input): return input")

    return temp_dir


@pytest.fixture
def project_details() -> ProjectDetails:
    if os.path.isfile("mocks/pyproject.toml"):
        with open("mocks/pyproject.toml", "r") as file:
            data = file.read()
    else:
        with open("tests/cli/mocks/pyproject.toml", "r") as file:
            data = file.read()
    return ProjectDetails.from_toml(data)


@pytest.fixture
def uipath_json() -> UiPathJson:
    if os.path.isfile("mocks/uipath-mock.json"):
        with open("mocks/uipath-mock.json", "r") as file:
            data = file.read()
    else:
        with open("tests/cli/mocks/uipath-mock.json", "r") as file:
            data = file.read()
    return UiPathJson.from_json(data)
