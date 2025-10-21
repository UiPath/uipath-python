#!/usr/bin/env python3
"""Script to update AGENTS.md reference files with complete library documentation.

This script extracts information from the uipath SDK and CLI commands and updates
the AGENTS.md reference files with comprehensive documentation including
- API Reference (SDK services and methods)
- CLI Commands Reference
"""

import inspect
import sys
from io import StringIO
from pathlib import Path
from typing import Any, Dict

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


def extract_method_signature(method: Any, include_types: bool = True) -> str:
    """Extract a clean method signature from a method object.

    Args:
        method: The method to extract signature from
        include_types: Whether to include type annotations

    Returns:
        String representation of the method signature
    """
    try:
        sig = inspect.signature(method)
        params = []
        for name, param in sig.parameters.items():
            if name in ("self", "cls"):
                continue

            param_str = name
            if include_types and param.annotation != inspect.Parameter.empty:
                type_str = str(param.annotation)
                type_str = type_str.replace("<class '", "").replace("'>", "")
                type_str = type_str.replace("typing.", "")
                param_str = f"{name}: {type_str}"

            if param.default != inspect.Parameter.empty:
                if param.kind == inspect.Parameter.VAR_POSITIONAL:
                    param_str = f"*{name}"
                elif param.kind == inspect.Parameter.VAR_KEYWORD:
                    param_str = f"**{name}"
                elif param.default is None:
                    param_str = f"{param_str}=None"
                elif isinstance(param.default, str):
                    param_str = f'{param_str}="{param.default}"'
                elif isinstance(param.default, bool):
                    param_str = f"{param_str}={param.default}"
                else:
                    param_str = f"{param_str}={param.default}"
            else:
                if param.kind == inspect.Parameter.VAR_POSITIONAL:
                    param_str = f"*{name}"
                elif param.kind == inspect.Parameter.VAR_KEYWORD:
                    param_str = f"**{name}"

            params.append(param_str)
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


def get_service_methods(service_class: type) -> list[tuple[str, Any]]:
    """Extract public methods from a service class.

    Args:
        service_class: The service class to extract methods from

    Returns:
        List of tuples (method_name, method_object) for public methods
    """
    methods = []
    for name in dir(service_class):
        if name.startswith("_"):
            continue
        attr = getattr(service_class, name, None)
        if callable(attr) and hasattr(attr, "__doc__") and attr.__doc__:
            methods.append((name, attr))
    return methods


def generate_quick_api_docs() -> str:
    """Generate API Reference documentation for SDK.

    Returns:
        Markdown string with SDK API documentation
    """
    from uipath import UiPath

    output = StringIO()
    output.write("\n## API Reference\n\n")
    output.write(
        "This section provides a comprehensive reference for all UiPath SDK services and methods. "
        "Each service is documented with complete method signatures, including parameter types and return types.\n\n"
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

    uipath_properties = []
    for name in dir(UiPath):
        if name.startswith("_"):
            continue
        attr = getattr(UiPath, name, None)
        if isinstance(attr, property):
            uipath_properties.append(name)

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

            return_annotation = None
            if service_property.fget:
                property_sig = inspect.signature(service_property.fget)
                return_annotation = property_sig.return_annotation

            output.write(f"### {service_name.replace('_', ' ').title()}\n\n")
            output.write(f"{description}\n\n")
            output.write("```python\n")

            if return_annotation and return_annotation != inspect.Signature.empty:
                service_class = return_annotation
                methods = get_service_methods(service_class)

                if methods:
                    for method_name, method in methods:
                        try:
                            if callable(method):
                                method_sig = extract_method_signature(method)
                                doc = get_first_line(inspect.getdoc(method) or "")

                                return_type = ""
                                try:
                                    sig = inspect.signature(method)
                                    if sig.return_annotation != inspect.Signature.empty:
                                        return_type_str = str(sig.return_annotation)
                                        return_type_str = return_type_str.replace(
                                            "<class '", ""
                                        ).replace("'>", "")
                                        return_type = f" -> {return_type_str}"
                                except Exception:
                                    pass

                                output.write(f"# {doc}\n" if doc else "")
                                output.write(
                                    f"sdk.{service_name}.{method_name}{method_sig}{return_type}\n\n"
                                )
                        except Exception:
                            continue
                else:
                    output.write(f"# Access {service_name} service methods\n")
                    output.write(f"service = sdk.{service_name}\n\n")

            output.write("```\n\n")
        except Exception:
            continue

    return output.getvalue()


def generate_cli_docs() -> str:
    """Generate CLI documentation markdown.

    Returns:
        Markdown string with CLI commands documentation
    """
    from uipath._cli import (
        eval,
        init,
        run,
    )

    commands = [
        ("init", init),
        ("run", run),
        ("eval", eval),
    ]

    output = StringIO()
    output.write("\n## CLI Commands Reference\n\n")
    output.write(
        "The UiPath Python SDK provides a comprehensive CLI for managing coded agents and automation projects. "
        "All commands should be executed with `uv run uipath <command>`.\n\n"
    )

    output.write("### Command Overview\n\n")
    output.write("| Command | Purpose | When to Use |\n")
    output.write("|---------|---------|-------------|\n")
    output.write(
        "| `init` | Initialize agent project | Creating a new agent or updating schema |\n"
    )
    output.write("| `run` | Execute agent | Running agent locally or testing |\n")
    output.write(
        "| `eval` | Evaluate agent | Testing agent performance with evaluation sets |\n\n"
    )

    output.write("---\n\n")

    for cmd_name, cmd in commands:
        cmd_info = get_command_help(cmd, cmd_name)

        output.write(f"### `uipath {cmd_name}`\n\n")
        output.write(f"**Description:** {cmd_info['help']}\n\n")

        arguments = [p for p in cmd_info["params"] if p["type"] == "Argument"]
        options = [p for p in cmd_info["params"] if p["type"] == "Option"]

        if arguments:
            output.write("**Arguments:**\n\n")
            output.write("| Argument | Required | Description |\n")
            output.write("|----------|----------|-------------|\n")
            for arg in arguments:
                required = "Yes" if arg.get("required") else "No"
                help_text = arg["help"] if arg["help"] else "N/A"
                output.write(f"| `{arg['name']}` | {required} | {help_text} |\n")
            output.write("\n")

        if options:
            output.write("**Options:**\n\n")
            output.write("| Option | Type | Default | Description |\n")
            output.write("|--------|------|---------|-------------|\n")
            for opt in options:
                opts_str = ", ".join(f"`{o}`" for o in opt.get("opts", []))

                if opt.get("is_flag"):
                    opt_type = "flag"
                    default = "false"
                elif opt.get("default") is not None:
                    opt_type = "value"
                    default_val = opt["default"]
                    if isinstance(default_val, str):
                        default = f'`"{default_val}"`'
                    else:
                        default = f"`{default_val}`"
                else:
                    opt_type = "value"
                    default = "none"

                help_text = opt["help"] if opt["help"] else "N/A"
                output.write(f"| {opts_str} | {opt_type} | {default} | {help_text} |\n")
            output.write("\n")

        output.write("**Usage Examples:**\n\n")

        if cmd_name == "init":
            output.write("```bash\n")
            output.write("# Initialize a new agent project\n")
            output.write("uv run uipath init\n\n")
            output.write("# Initialize with specific entrypoint\n")
            output.write("uv run uipath init main.py\n\n")
            output.write("# Initialize and infer bindings from code\n")
            output.write("uv run uipath init --infer-bindings\n")
            output.write("```\n\n")
            output.write(
                "**When to use:** Run this command when you've modified the Input/Output models and need to regenerate the `uipath.json` schema file.\n\n"
            )

        elif cmd_name == "run":
            output.write("```bash\n")
            output.write("# Run agent with inline JSON input\n")
            output.write(
                'uv run uipath run main.py \'{"query": "What is the weather?"}\'\n\n'
            )
            output.write("# Run agent with input from file\n")
            output.write("uv run uipath run main.py --file input.json\n\n")
            output.write("# Run agent and save output to file\n")
            output.write(
                'uv run uipath run agent \'{"task": "Process data"}\' --output-file result.json\n\n'
            )
            output.write("# Run agent with debugging enabled\n")
            output.write(
                'uv run uipath run main.py \'{"input": "test"}\' --debug --debug-port 5678\n\n'
            )
            output.write("# Resume agent execution from previous state\n")
            output.write("uv run uipath run --resume\n")
            output.write("```\n\n")
            output.write(
                "**When to use:** Run this command to execute your agent locally for development, testing, or debugging. Use `--debug` flag to attach a debugger for step-by-step debugging.\n\n"
            )

        elif cmd_name == "eval":
            output.write("```bash\n")
            output.write("# Run evaluation with auto-discovered files\n")
            output.write("uv run uipath eval\n\n")
            output.write("# Run evaluation with specific entrypoint and eval set\n")
            output.write("uv run uipath eval main.py eval_set.json\n\n")
            output.write("# Run evaluation without reporting results\n")
            output.write("uv run uipath eval --no-report\n\n")
            output.write("# Run evaluation with custom number of workers\n")
            output.write("uv run uipath eval --workers 4\n\n")
            output.write("# Save evaluation output to file\n")
            output.write("uv run uipath eval --output-file eval_results.json\n")
            output.write("```\n\n")
            output.write(
                "**When to use:** Run this command to test your agent's performance against a predefined evaluation set. This helps validate agent behavior and measure quality metrics.\n\n"
            )

        output.write("---\n\n")

    output.write("### Common Workflows\n\n")
    output.write("**1. Creating a New Agent:**\n")
    output.write("```bash\n")
    output.write("# Step 1: Initialize project\n")
    output.write("uv run uipath init\n\n")
    output.write("# Step 2: Run agent to test\n")
    output.write('uv run uipath run main.py \'{"input": "test"}\'\n\n')
    output.write("# Step 3: Evaluate agent performance\n")
    output.write("uv run uipath eval\n")
    output.write("```\n\n")

    output.write("**2. Development & Testing:**\n")
    output.write("```bash\n")
    output.write("# Run with debugging\n")
    output.write('uv run uipath run main.py \'{"input": "test"}\' --debug\n\n')
    output.write("# Test with input file\n")
    output.write(
        "uv run uipath run main.py --file test_input.json --output-file test_output.json\n"
    )
    output.write("```\n\n")

    output.write("**3. Schema Updates:**\n")
    output.write("```bash\n")
    output.write("# After modifying Input/Output models, regenerate schema\n")
    output.write("uv run uipath init --infer-bindings\n")
    output.write("```\n\n")

    output.write("### Configuration File (uipath.json)\n\n")
    output.write(
        "The `uipath.json` file is automatically generated by `uipath init` and defines your agent's schema and bindings.\n\n"
    )

    output.write("**Structure:**\n\n")
    output.write("```json\n")
    output.write("{\n")
    output.write('  "entryPoints": [\n')
    output.write("    {\n")
    output.write('      "filePath": "agent",\n')
    output.write('      "uniqueId": "uuid-here",\n')
    output.write('      "type": "agent",\n')
    output.write('      "input": {\n')
    output.write('        "type": "object",\n')
    output.write('        "properties": { ... },\n')
    output.write('        "description": "Input schema",\n')
    output.write('        "required": [ ... ]\n')
    output.write("      },\n")
    output.write('      "output": {\n')
    output.write('        "type": "object",\n')
    output.write('        "properties": { ... },\n')
    output.write('        "description": "Output schema",\n')
    output.write('        "required": [ ... ]\n')
    output.write("      }\n")
    output.write("    }\n")
    output.write("  ],\n")
    output.write('  "bindings": {\n')
    output.write('    "version": "2.0",\n')
    output.write('    "resources": []\n')
    output.write("  }\n")
    output.write("}\n")
    output.write("```\n\n")

    output.write("**When to Update:**\n\n")
    output.write(
        "1. **After Modifying Input/Output Models**: Run `uv run uipath init --infer-bindings` to regenerate schemas\n"
    )
    output.write(
        "2. **Changing Entry Point**: Update `filePath` if you rename or move your main file\n"
    )
    output.write(
        "3. **Manual Schema Adjustments**: Edit `input.jsonSchema` or `output.jsonSchema` directly if needed\n"
    )
    output.write(
        "4. **Bindings Updates**: The `bindings` section maps the exported graph variable - update if you rename your graph\n\n"
    )

    output.write("**Important Notes:**\n\n")
    output.write("- The `uniqueId` should remain constant for the same agent\n")
    output.write('- Always use `type: "agent"` for LangGraph agents\n')
    output.write("- The `jsonSchema` must match your Pydantic models exactly\n")
    output.write(
        "- Re-run `uipath init --infer-bindings` instead of manual edits when possible\n\n"
    )

    return output.getvalue()


def generate_agents_md_reference_files() -> None:
    """Generate separate reference files."""
    resources_dir = Path(__file__).parent.parent / "src" / "uipath" / "_resources"

    sdk_reference_path = resources_dir / "SDK_REFERENCE.md"
    cli_reference_path = resources_dir / "CLI_REFERENCE.md"

    api_docs = generate_quick_api_docs()
    cli_docs = generate_cli_docs()

    with open(sdk_reference_path, "w", encoding="utf-8") as f:
        f.write(api_docs.lstrip("\n"))

    with open(cli_reference_path, "w", encoding="utf-8") as f:
        f.write(cli_docs.lstrip("\n"))


def main():
    """Main function."""
    try:
        generate_agents_md_reference_files()
    except Exception as e:
        print(f"Error updating AGENTS.md reference files: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
