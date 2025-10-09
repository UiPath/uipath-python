#!/usr/bin/env python3
"""Script to update AGENTS.md with complete library documentation.

This script extracts information from the uipath SDK and CLI commands and updates
the AGENTS.md file with comprehensive documentation including
- SDK version
- Quick API Reference (SDK services and methods)
- CLI Commands Reference
"""

import inspect
import sys
from io import StringIO
from pathlib import Path
from typing import Any, Dict

# Add the src directory to the path to import from a local source
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import click


def get_command_help(command: click.Command, command_name: str) -> Dict[str, Any]:
    """Extract help information from a Click command.

    Args:
        command: The Click command to extract help from
        command_name: The name of the command

    Returns:
        Dictionary with command information
    """
    help_text = command.help or "No description available."
    params = []
    for param in command.params:
        param_info = {
            "name": param.name,
            "type": type(param).__name__,
            "help": getattr(param, "help", "") or "",
            "required": param.required,
        }

        if isinstance(param, click.Option):
            param_info["opts"] = param.opts
            param_info["is_flag"] = param.is_flag
            if param.default is not None and not param.is_flag:
                param_info["default"] = param.default
        elif isinstance(param, click.Argument):
            param_info["opts"] = [param.name]

        params.append(param_info)

    return {
        "name": command_name,
        "help": help_text,
        "params": params,
    }


def get_version() -> str:
    """Get the version from pyproject.toml.

    Returns:
        Version string
    """
    import tomli

    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        data = tomli.load(f)
        return data.get("project", {}).get("version", "unknown")


def extract_method_signature(method: Any) -> str:
    """Extract a clean method signature from a method object.

    Args:
        method: The method to extract signature from

    Returns:
        String representation of the method signature
    """
    try:
        sig = inspect.signature(method)
        params = []
        for name, param in sig.parameters.items():
            if name in ("self", "cls"):
                continue
            if param.default == inspect.Parameter.empty:
                if param.kind == inspect.Parameter.VAR_POSITIONAL:
                    params.append(f"*{name}")
                elif param.kind == inspect.Parameter.VAR_KEYWORD:
                    params.append(f"**{name}")
                else:
                    params.append(name)
            else:
                if param.default is None:
                    params.append(f"{name}=None")
                elif isinstance(param.default, str):
                    params.append(f'{name}="{param.default}"')
                else:
                    params.append(f"{name}={param.default}")
        return f"({', '.join(params)})"
    except Exception:
        return "()"


def get_first_line(docstring: str) -> str:
    """Get the first meaningful line from a docstring.

    Args:
        docstring: The docstring to process

    Returns:
        First line of the docstring
    """
    if not docstring:
        return ""
    lines = docstring.strip().split("\n")
    for line in lines:
        stripped = line.strip()
        if (
            stripped
            and not stripped.startswith("Args:")
            and not stripped.startswith("Returns:")
        ):
            return stripped
    return ""


def get_service_methods(service_class: type) -> list[str]:
    """Extract public methods from a service class.

    Args:
        service_class: The service class to extract methods from

    Returns:
        List of method names (excluding private/internal methods)
    """
    methods = []
    for name in dir(service_class):
        if name.startswith("_"):
            continue
        attr = getattr(service_class, name, None)
        if callable(attr) and hasattr(attr, "__doc__") and attr.__doc__:
            methods.append(name)
    return methods[:3]  # Limit to first 3 methods for brevity


def generate_quick_api_docs() -> str:
    """Generate Quick API Reference documentation for SDK.

    Returns:
        Markdown string with SDK API documentation
    """
    from uipath import UiPath

    output = StringIO()
    output.write("\n## Quick API Reference\n\n")
    output.write(
        "This section provides a concise reference for the most commonly used UiPath SDK methods.\n\n"
    )

    output.write("### SDK Initialization\n\n")
    output.write("Initialize the UiPath SDK client\n\n")
    output.write("```python\n")
    output.write("from uipath import UiPath\n\n")
    output.write("# Initialize with environment variables\n")
    output.write("sdk = UiPath()\n\n")
    output.write("# Or with explicit credentials\n")
    output.write(
        'sdk = UiPath(base_url="https://cloud.uipath.com/...", secret="your_token")\n'
    )
    output.write("```\n\n")

    # Dynamically discover all service properties from UiPath class
    uipath_properties = []
    for name in dir(UiPath):
        if name.startswith("_"):
            continue
        attr = getattr(UiPath, name, None)
        if isinstance(attr, property):
            uipath_properties.append(name)

    # Sort for consistent output
    uipath_properties.sort()

    for service_name in uipath_properties:
        try:
            service_property = getattr(UiPath, service_name)
            if not isinstance(service_property, property):
                continue

            service_doc = (
                service_property.fget.__doc__ if service_property.fget else None
            )

            description = (
                service_doc.strip().split("\n")[0]
                if service_doc
                else f"{service_name.replace('_', ' ').title()} service"
            )

            output.write(f"### {service_name.replace('_', ' ').title()}\n\n")
            output.write(f"{description}\n\n")
            output.write("```python\n")

            return_annotation = None
            if service_property.fget:
                property_sig = inspect.signature(service_property.fget)
                return_annotation = property_sig.return_annotation

            if return_annotation and return_annotation != inspect.Signature.empty:
                service_class = return_annotation
                methods = get_service_methods(service_class)

                for method_name in methods:
                    try:
                        method = getattr(service_class, method_name)
                        if callable(method):
                            method_sig = extract_method_signature(method)
                            doc = get_first_line(inspect.getdoc(method) or "")

                            output.write(f"# {doc}\n" if doc else "")
                            output.write(
                                f"sdk.{service_name}.{method_name}{method_sig}\n\n"
                            )
                    except Exception:
                        continue

            output.write("```\n\n")
        except Exception:
            continue

    output.write(
        "For complete API documentation, visit: https://uipath.github.io/uipath-python/\n\n"
    )

    return output.getvalue()


def generate_cli_docs() -> str:
    """Generate CLI documentation markdown.

    Returns:
        Markdown string with CLI commands documentation
    """
    from uipath._cli import (
        auth,
        deploy,
        dev,
        eval,
        init,
        invoke,
        new,
        pack,
        publish,
        pull,
        push,
        run,
    )

    commands = [
        ("new", new),
        ("init", init),
        ("run", run),
        ("pack", pack),
        ("publish", publish),
        ("deploy", deploy),
        ("invoke", invoke),
        ("push", push),
        ("pull", pull),
        ("eval", eval),
        ("dev", dev),
        ("auth", auth),
    ]

    version = get_version()

    output = StringIO()
    output.write("\n---\n\n")
    output.write("## CLI Commands Reference\n\n")
    output.write(f"**UiPath Python SDK Version:** `{version}`\n\n")
    output.write(
        "The UiPath Python SDK provides a comprehensive CLI for managing coded agents and automation projects.\n\n"
    )

    for cmd_name, cmd in commands:
        cmd_info = get_command_help(cmd, cmd_name)

        output.write(f"### `uipath {cmd_name}`\n\n")
        output.write(f"{cmd_info['help']}\n\n")

        arguments = [p for p in cmd_info["params"] if p["type"] == "Argument"]
        options = [p for p in cmd_info["params"] if p["type"] == "Option"]

        if arguments:
            output.write("**Arguments:**\n\n")
            for arg in arguments:
                required = " (required)" if arg.get("required") else " (optional)"
                output.write(f"- `{arg['name']}`{required}")
                if arg["help"]:
                    output.write(f": {arg['help']}")
                output.write("\n")
            output.write("\n")

        if options:
            output.write("**Options:**\n\n")
            for opt in options:
                opts_str = ", ".join(f"`{o}`" for o in opt.get("opts", []))
                output.write(f"- {opts_str}")

                if opt.get("is_flag"):
                    output.write(" (flag)")
                elif opt.get("default") is not None:
                    output.write(f" (default: `{opt['default']}`)")

                if opt["help"]:
                    output.write(f": {opt['help']}")
                output.write("\n")
            output.write("\n")

        output.write("**Example:**\n\n")
        output.write("```bash\n")

        if cmd_name == "new":
            output.write("uipath new my-agent\n")
        elif cmd_name == "init":
            output.write("uipath init\n")
        elif cmd_name == "run":
            output.write('uipath run main.py \'{"input": "value"}\'\n')
        elif cmd_name == "pack":
            output.write("uipath pack\n")
        elif cmd_name == "publish":
            output.write("uipath publish\n")
        elif cmd_name == "deploy":
            output.write("uipath deploy my-process\n")
        elif cmd_name == "invoke":
            output.write('uipath invoke my-process \'{"input": "value"}\'\n')
        elif cmd_name == "push":
            output.write("uipath push\n")
        elif cmd_name == "pull":
            output.write("uipath pull my-process\n")
        elif cmd_name == "eval":
            output.write("uipath eval\n")
        elif cmd_name == "dev":
            output.write("uipath dev\n")
        elif cmd_name == "auth":
            output.write("uipath auth login\n")

        output.write("```\n\n")

    output.write("---\n\n")
    output.write("For more information on any command, run:\n")
    output.write("```bash\n")
    output.write("uipath <command> --help\n")
    output.write("```\n")

    return output.getvalue()


def update_agents_md() -> None:
    """Update the AGENTS.md file with API and CLI documentation."""
    agents_md_path = (
        Path(__file__).parent.parent / "src" / "uipath" / "_resources" / "AGENTS.md"
    )

    if not agents_md_path.exists():
        print(f"Error: AGENTS.md not found at {agents_md_path}", file=sys.stderr)
        sys.exit(1)

    with open(agents_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    api_marker = "## Quick API Reference"
    cli_marker = "## CLI Commands Reference"

    # Preserve manually written agent patterns
    if api_marker in content:
        content = content.split(api_marker)[0].rstrip()
    elif cli_marker in content:
        content = content.split(cli_marker)[0].rstrip()

    api_docs = generate_quick_api_docs()
    cli_docs = generate_cli_docs()
    updated_content = content + "\n" + api_docs + cli_docs

    with open(agents_md_path, "w", encoding="utf-8") as f:
        f.write(updated_content)

    print(f"Successfully updated {agents_md_path}")


def main():
    """Main function."""
    try:
        update_agents_md()
    except Exception as e:
        print(f"Error updating AGENTS.md: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
