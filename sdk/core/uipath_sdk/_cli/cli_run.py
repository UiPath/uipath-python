# type: ignore
import importlib.util
import inspect
import json
import logging
import os
import traceback
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional, Type, TypeVar, get_type_hints

import click

from .middlewares import Middlewares

logger = logging.getLogger(__name__)

T = TypeVar("T")


def convert_to_class(data: Dict[str, Any], cls: Type[T]) -> T:
    """Convert a dictionary to either a dataclass or regular class instance."""
    if is_dataclass(cls):
        field_types = get_type_hints(cls)
        converted_data = {}

        for field_name, field_type in field_types.items():
            if field_name not in data:
                continue

            value = data[field_name]
            if (
                is_dataclass(field_type) or hasattr(field_type, "__annotations__")
            ) and isinstance(value, dict):
                value = convert_to_class(value, field_type)
            converted_data[field_name] = value

        return cls(**converted_data)
    else:
        sig = inspect.signature(cls.__init__)
        params = sig.parameters

        init_args = {}

        for param_name, param in params.items():
            if param_name == "self":
                continue

            if param_name in data:
                value = data[param_name]
                param_type = (
                    param.annotation
                    if param.annotation != inspect.Parameter.empty
                    else Any
                )

                if (
                    is_dataclass(param_type) or hasattr(param_type, "__annotations__")
                ) and isinstance(value, dict):
                    value = convert_to_class(value, param_type)

                init_args[param_name] = value
            elif param.default != inspect.Parameter.empty:
                init_args[param_name] = param.default

        return cls(**init_args)


def convert_from_class(obj: Any) -> Dict[str, Any]:
    """Convert a class instance (dataclass or regular) to a dictionary."""
    if obj is None:
        return None

    if is_dataclass(obj):
        return asdict(obj)
    elif hasattr(obj, "__dict__"):
        result = {}
        for key, value in obj.__dict__.items():
            # Skip private attributes
            if not key.startswith("_"):
                if hasattr(value, "__dict__") or is_dataclass(value):
                    result[key] = convert_from_class(value)
                else:
                    result[key] = value
        return result
    return obj


def execute_python_script(
    script_path: str, input_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute the Python script with the given input."""

    spec = importlib.util.spec_from_file_location("dynamic_module", script_path)
    if not spec or not spec.loader:
        raise ImportError(f"Could not load spec for {script_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for func_name in ["main", "run", "execute"]:
        if hasattr(module, func_name):
            main_func = getattr(module, func_name)
            sig = inspect.signature(main_func)
            params = list(sig.parameters.values())

            # Case 1: No parameters
            if not params:
                result = main_func()
                return convert_from_class(result) if result is not None else {}

            input_param = params[0]
            input_type = input_param.annotation

            # Case 2: Class or dataclass parameter
            if input_type != inspect.Parameter.empty and (
                is_dataclass(input_type) or hasattr(input_type, "__annotations__")
            ):
                typed_input = convert_to_class(input_data, input_type)
                result = main_func(typed_input)
                return convert_from_class(result) if result is not None else {}

            # Case 3: Dict parameter
            else:
                result = main_func(input_data)
                return convert_from_class(result) if result is not None else {}

    raise ValueError(f"No main function (main, run, or execute) found in {script_path}")


@click.command()
@click.argument("entrypoint", required=False)
@click.argument("input", required=False, default="{}")
@click.option("--resume", is_flag=True, help="Resume execution from a previous state")
def run(entrypoint: Optional[str], input: Optional[str], resume: bool) -> None:
    """Execute a Python script with JSON input."""
    result = Middlewares.next("run", entrypoint, input, resume)

    if result.error_message:
        click.echo(result.error_message)
        if result.should_include_stacktrace:
            click.echo(traceback.format_exc())
        click.get_current_context().exit(1)

    if result.info_message:
        click.echo(result.info_message)

    if not result.should_continue:
        return

    if not entrypoint:
        click.echo("""Error: No entrypoint specified. Please provide a path to a Python script.
Usage: `uipath run <entrypoint_path> <input_arguments>`""")
        click.get_current_context().exit(1)

    if not os.path.exists(entrypoint):
        click.echo(f"""Error: Script not found at path {entrypoint}.
Usage: `uipath run <entrypoint_path> <input_arguments>`""")
        click.get_current_context().exit(1)

    try:
        try:
            input_data = json.loads(input)
        except json.JSONDecodeError:
            click.echo("Error: Invalid JSON input data")
            click.get_current_context().exit(1)

        result = execute_python_script(entrypoint, input_data)
        print(f"[OutputStart]{json.dumps(result)}[OutputEnd]")

    except Exception as e:
        click.echo(f"Error: {str(e)}")
        click.echo(traceback.format_exc())
        click.get_current_context().exit(1)


if __name__ == "__main__":
    run()
