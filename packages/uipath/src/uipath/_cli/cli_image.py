import json
import re
import subprocess
from pathlib import Path
from typing import Any

import click

from uipath._cli._utils._console import ConsoleLogger
from uipath._cli._utils._project_files import read_toml_project

from ._telemetry import track_command

console = ConsoleLogger()

CONTAINER_MANIFEST_SCHEMA = "https://cloud.uipath.com/draft/2026-06/container-image"
DEFAULT_OUTPUT_DIR = ".uipath/image"
DEFAULT_PYTHON_VERSION = "3.11"


@click.group()
def image() -> None:
    """Build and publish UiPath container image artifacts."""


@image.command(name="build")
@click.argument(
    "root",
    required=False,
    default=".",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
@click.option("--tag", "image_tag", type=str, help="Container image tag to build.")
@click.option(
    "--entrypoint",
    "entrypoint",
    type=str,
    help="mcp.json server name to run (required if multiple servers).",
)
@click.option(
    "--output-dir",
    default=DEFAULT_OUTPUT_DIR,
    show_default=True,
    type=click.Path(file_okay=False),
    help="Directory for generated artifacts.",
)
@click.option("--base-image", type=str, help="Base image for the generated Dockerfile.")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Generate artifacts and print the docker command without running Docker.",
)
@track_command("image-build")
def build(
    root: str,
    image_tag: str | None,
    entrypoint: str | None,
    output_dir: str,
    base_image: str | None,
    dry_run: bool,
) -> None:
    """Build a Docker image for a coded UiPath MCP project."""
    project_root = Path(root).resolve()
    out = (
        (project_root / output_dir).resolve()
        if not Path(output_dir).is_absolute()
        else Path(output_dir)
    )
    out.mkdir(parents=True, exist_ok=True)

    project = read_toml_project(str(project_root / "pyproject.toml"))
    server = _resolve_entrypoint(project_root, entrypoint)
    py = _python_version(project.get("requires-python"))
    base_image = base_image or f"ghcr.io/astral-sh/uv:python{py}-bookworm-slim"
    image_tag = (
        image_tag or f"uipath/{_safe(project['name'])}:{_safe(project['version'])}"
    )

    (out / "Dockerfile").write_text(_dockerfile(base_image, server), encoding="utf-8")
    (out / ".dockerignore").write_text(
        _dockerignore(out, project_root), encoding="utf-8"
    )
    (out / "container-manifest.json").write_text(
        json.dumps(_manifest(image_tag, base_image, project, server), indent=2) + "\n",
        encoding="utf-8",
    )

    cmd = [
        "docker",
        "build",
        "-f",
        str(out / "Dockerfile"),
        "-t",
        image_tag,
        str(project_root),
    ]
    console.success(f"Generated image artifacts in {out}")
    if dry_run:
        click.echo(" ".join(cmd))
        return
    subprocess.run(cmd, check=True)


def _resolve_entrypoint(project_root: Path, override: str | None) -> str:
    """Return the mcp.json server name to run (the AgentHub slug)."""
    if override:
        return override
    mcp = project_root / "mcp.json"
    if not mcp.exists():
        console.error("mcp.json not found; run `uipath init` for an MCP project.")
    servers = json.loads(mcp.read_text(encoding="utf-8")).get("servers", {})
    names = list(servers.keys())
    if len(names) != 1:
        console.error(
            f"Expected exactly one server in mcp.json, found {names}; pass --entrypoint."
        )
    return names[0]


def _python_version(requires_python: str | None) -> str:
    """Extract Python version string from requires-python specifier."""
    if not requires_python:
        return DEFAULT_PYTHON_VERSION
    m = re.search(r"(3)\.(\d+)", requires_python)
    return f"{m.group(1)}.{m.group(2)}" if m else DEFAULT_PYTHON_VERSION


def _safe(value: str) -> str:
    """Normalize a string to a safe Docker tag component."""
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip(".-_") or "project"


def _dockerfile(base_image: str, server: str) -> str:
    """Generate Dockerfile content for an MCP project."""
    return "\n".join(
        [
            f"FROM {base_image}",
            "",
            "WORKDIR /app",
            "ENV PYTHONUNBUFFERED=1 \\",
            "    UV_LINK_MODE=copy \\",
            "    UV_COMPILE_BYTECODE=1 \\",
            '    PATH="/app/.venv/bin:$PATH"',
            "",
            "COPY . .",
            "RUN if [ -f uv.lock ]; then uv sync --frozen --no-dev; else uv sync --no-dev; fi",
            "",
            'ENTRYPOINT ["uipath", "run"]',
            f'CMD ["{server}"]',
            "",
        ]
    )


def _dockerignore(out: Path, root: Path) -> str:
    """Generate .dockerignore content, excluding the output dir if inside root."""
    rel = out.relative_to(root).as_posix() if out.is_relative_to(root) else ""
    entries = [
        ".git",
        ".venv",
        "__pycache__/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".mypy_cache/",
        "*.pyc",
    ]
    if rel:
        entries.append(rel)
    return "\n".join(entries) + "\n"


def _manifest(
    image_tag: str, base_image: str, project: dict[str, Any], server: str
) -> dict[str, Any]:
    """Generate container-manifest.json content."""
    return {
        "$schema": CONTAINER_MANIFEST_SCHEMA,
        "image": image_tag,
        "baseImage": base_image,
        "projectName": project["name"],
        "version": project["version"],
        "targetRuntime": "python",
        "defaultEntrypoint": server,
        "command": ["uipath", "run", server],
        "labels": {
            "com.uipath.project.name": project["name"],
            "com.uipath.project.version": project["version"],
            "com.uipath.artifact.kind": "coded-mcp-container",
        },
    }
