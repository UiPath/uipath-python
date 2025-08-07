import os
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from click.testing import CliRunner

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
