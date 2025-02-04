import os
import tempfile
from typing import Generator

import pytest
from click.testing import CliRunner


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
