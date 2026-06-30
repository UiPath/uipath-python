import json
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from uipath._cli import cli

docker_available = (
    shutil.which("docker") is not None
    and subprocess.run(["docker", "info"], capture_output=True).returncode == 0
)


def _scaffold(tmp: Path) -> None:
    (tmp / "pyproject.toml").write_text(
        '[project]\nname = "invoice-mcp"\nversion = "1.2.3"\n'
        'description = "Invoice MCP server"\n'
        'requires-python = ">=3.12"\ndependencies = ["uipath-mcp>=0.1.0"]\n',
        encoding="utf-8",
    )
    # mcp.json server name is the authoritative slug / run argument
    (tmp / "mcp.json").write_text(
        json.dumps(
            {"servers": {"invoice": {"command": "python", "args": ["server.py"]}}}
        ),
        encoding="utf-8",
    )
    (tmp / "server.py").write_text("# server\n", encoding="utf-8")


def test_image_build_dry_run_generates_artifacts(
    runner: CliRunner, temp_dir: str
) -> None:
    with runner.isolated_filesystem(temp_dir=temp_dir):
        _scaffold(Path("."))
        result = runner.invoke(cli, ["image", "build", "--dry-run"], env={})
        assert result.exit_code == 0, result.output
        assert "docker build" in result.output

        out = Path(".uipath/image")
        dockerfile = (out / "Dockerfile").read_text(encoding="utf-8")
        manifest = json.loads(
            (out / "container-manifest.json").read_text(encoding="utf-8")
        )

        assert "FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim" in dockerfile
        assert 'ENTRYPOINT ["uipath", "run"]' in dockerfile
        # entrypoint is the mcp.json server name, NOT a file path
        assert 'CMD ["invoice"]' in dockerfile
        assert manifest["command"] == ["uipath", "run", "invoice"]
        assert manifest["defaultEntrypoint"] == "invoice"
        assert manifest["image"] == "uipath/invoice-mcp:1.2.3"

        dockerignore = (out / ".dockerignore").read_text(encoding="utf-8")
        assert ".git" in dockerignore
        assert ".venv" in dockerignore
        assert (
            ".uipath/image" in dockerignore
        )  # output dir excluded from its own build context


@pytest.mark.skipif(not docker_available, reason="docker not available")
def test_image_build_produces_runnable_image(runner: CliRunner, temp_dir: str) -> None:
    """Build the image and verify uipath CLI is on PATH (so 'uipath run' works)."""
    with runner.isolated_filesystem(temp_dir=temp_dir):
        _scaffold(Path("."))
        # Build the real image (no --dry-run); network required for uv sync
        result = runner.invoke(
            cli, ["image", "build", "--tag", "uipath-itest/invoice:0"], env={}
        )
        assert result.exit_code == 0, result.output
        # The image must expose the uipath CLI on PATH
        inspect = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "uipath",
                "uipath-itest/invoice:0",
                "--help",
            ],
            capture_output=True,
            text=True,
        )
        assert inspect.returncode == 0, inspect.stderr
        assert "run" in inspect.stdout
