import os
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from click.testing import CliRunner

from tests.utils.project_details import ProjectDetails
from tests.utils.uipath_json import UiPathJson
from uipath._execution_context import ExecutionContext

# Ensure local source package (src/uipath) is importable before tests collect
_PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
_SRC_PATH: Path = _PROJECT_ROOT / "src"
if _SRC_PATH.exists():
    sys.path.insert(0, str(_SRC_PATH))


@pytest.fixture
def runner() -> CliRunner:
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clean environment variables before each test."""
    monkeypatch.delenv("UIPATH_URL", raising=False)
    monkeypatch.delenv("UIPATH_ACCESS_TOKEN", raising=False)


@pytest.fixture
def execution_context(monkeypatch: pytest.MonkeyPatch) -> ExecutionContext:
    """Provide an execution context for testing."""
    monkeypatch.setenv("UIPATH_ROBOT_KEY", "test-robot-key")
    return ExecutionContext()


@pytest.fixture
def mock_project(temp_dir: str) -> str:
    """Create a mock project structure for testing."""
    # Create sample files
    with open(os.path.join(temp_dir, "main.py"), "w") as f:
        f.write("def main(input): return input")

    return temp_dir


@pytest.fixture
def project_details() -> ProjectDetails:
    if os.path.isfile("../utils/mocks/pyproject.toml"):
        with open("../utils/mocks/pyproject.toml", "r") as file:
            data = file.read()
    else:
        with open("tests/utils/mocks/pyproject.toml", "r") as file:
            data = file.read()
    return ProjectDetails.from_toml(data)


@pytest.fixture
def uipath_json() -> UiPathJson:
    file_name = "uipath-mock.json"
    if os.path.isfile(f"../utils/mocks/{file_name}"):
        with open(f"../utils/mocks/{file_name}", "r") as file:
            data = file.read()
    else:
        with open(f"tests/utils/mocks/{file_name}", "r") as file:
            data = file.read()
    return UiPathJson.from_json(data)


@pytest.fixture
def uipath_script_json() -> UiPathJson:
    file_name = "uipath-simple-script-mock.json"
    if os.path.isfile(f"../utils/mocks/{file_name}"):
        with open(f"../utils/mocks/{file_name}", "r") as file:
            data = file.read()
    else:
        with open(f"tests/utils/mocks/{file_name}", "r") as file:
            data = file.read()
    return UiPathJson.from_json(data)


@pytest.fixture
def simple_script() -> str:
    if os.path.isfile("../utils/mocks/simple_script.py"):
        with open("../utils/mocks/simple_script.py", "r") as file:
            data = file.read()
    else:
        with open("tests/utils/mocks/simple_script.py", "r") as file:
            data = file.read()
    return data
