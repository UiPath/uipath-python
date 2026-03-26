import json
from typing import Any

import click


def _get_option_info(param: click.Parameter) -> dict[str, Any]:
    info: dict[str, Any] = {"name": param.name}

    if isinstance(param, click.Option):
        info["flags"] = list(param.opts)
        if param.secondary_opts:
            info["flags"].extend(param.secondary_opts)
        if param.required:
            info["required"] = True
        if param.is_flag:
            info["is_flag"] = True
        if param.default is not None and not param.is_flag:
            if "Sentinel" in type(param.default).__name__:
                info["default"] = "unset"
            else:
                info["default"] = param.default
        if param.help:
            info["description"] = param.help

    if hasattr(param.type, "name"):
        info["type"] = param.type.name

    if isinstance(param.type, click.Choice):
        info["choices"] = list(param.type.choices)

    return info


def _get_command_info(
    cmd: click.Command, name: str, parent_ctx: click.Context | None = None
) -> dict[str, Any]:
    """Extract metadata from a Click command."""
    info: dict[str, Any] = {"name": name}

    if cmd.help:
        help_text = cmd.help.split("\n\n")[0].replace("\b", "").strip()
        info["description"] = help_text

    options = [
        _get_option_info(p)
        for p in cmd.params
        if isinstance(p, click.Option) and p.name != "help" and not p.hidden
    ]
    if options:
        info["options"] = options

    arguments = [
        {"name": p.name, "required": p.required}
        for p in cmd.params
        if isinstance(p, click.Argument)
    ]
    if arguments:
        info["arguments"] = arguments

    if isinstance(cmd, click.Group):
        sub_ctx = click.Context(cmd, parent=parent_ctx, info_name=name)
        subcommands = []
        for sub_name in cmd.list_commands(sub_ctx):
            sub_cmd = cmd.get_command(sub_ctx, sub_name)
            if sub_cmd:
                subcommands.append(_get_command_info(sub_cmd, sub_name, sub_ctx))
        if subcommands:
            info["subcommands"] = subcommands

    return info


def get_help_json(group: click.Group, ctx: click.Context, version: str) -> str:
    """Generate JSON help for the CLI.

    Args:
        group: The root CLI group
        ctx: Click context
        version: CLI version string

    Returns:
        JSON string with CLI structure
    """
    result: dict[str, Any] = {
        "name": ctx.info_name or "uipath",
        "version": version,
    }

    if group.help:
        result["description"] = group.help.split("\n\n")[0].replace("\b", "").strip()

    options = [
        _get_option_info(p)
        for p in group.params
        if isinstance(p, click.Option) and p.name != "help" and not p.hidden
    ]
    if options:
        result["options"] = options

    commands = []
    for cmd_name in group.list_commands(ctx):
        cmd = group.get_command(ctx, cmd_name)
        if cmd:
            commands.append(_get_command_info(cmd, cmd_name, ctx))

    result["commands"] = commands

    return json.dumps(result, indent=2, default=str)
