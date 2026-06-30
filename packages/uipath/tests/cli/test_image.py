import json
from pathlib import Path

from click.testing import CliRunner

from uipath._cli import cli


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
