# type: ignore
import importlib.util
import inspect
import json
import logging
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, get_type_hints

import click

from .middlewares import Middlewares

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
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


def find_python_files(directory: str = ".") -> List[Path]:
    """Find all Python files in the given directory."""
    return list(Path(directory).glob("*.py"))


def execute_python_script(
    script_path: str, input_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute the Python script with the given input."""
    try:
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

                if not params:
                    raise ValueError(
                        f"Function {func_name} must have at least one parameter"
                    )

                input_param = params[0]
                input_type = input_param.annotation

                # Check if input type is a class (either dataclass or regular)
                if input_type != inspect.Parameter.empty and (
                    is_dataclass(input_type) or hasattr(input_type, "__annotations__")
                ):
                    typed_input = convert_to_class(input_data, input_type)
                    result = main_func(typed_input)
                    return convert_from_class(result)
                else:
                    return main_func(input_data)

        raise ValueError(
            f"No main function (main, run, or execute) found in {script_path}"
        )

    except Exception as e:
        logger.error(f"Error executing Python script: {str(e)}")
        raise


@click.command()
@click.argument("input", required=False, default="{}")
@click.option("--entrypoint", "-e", help="The path to the Python script to execute")
def run(input: str, entrypoint: Optional[str] = None) -> None:
    """Execute a Python script with JSON input."""
    should_continue, errorMessage = Middlewares.next(
        "run", input, entrypoint=entrypoint
    )

    if errorMessage:
        click.echo(f"{errorMessage}")

    if not should_continue:
        return

    try:
        if not entrypoint:
            python_files = find_python_files()

            if not python_files:
                click.echo("No Python files found in the current directory.")
                return

            if len(python_files) == 1:
                entrypoint = str(python_files[0])
                click.echo(f"Using {entrypoint} as entrypoint")
            else:
                click.echo(
                    "Multiple Python files found. Please specify an entrypoint using `uipath run -e <file>`:"
                )
                for idx, file in enumerate(python_files, 1):
                    click.echo(f"  {idx}. {file}")
                return

        try:
            input_data = json.loads(input)
        except json.JSONDecodeError:
            click.echo("Invalid JSON input data")
            return

        result = execute_python_script(entrypoint, input_data)
        print(json.dumps(result))

    except FileNotFoundError:
        click.echo(f"Script not found: {entrypoint}")
    except Exception as e:
        click.echo(f"Error: {str(e)}")


if __name__ == "__main__":
    run()
