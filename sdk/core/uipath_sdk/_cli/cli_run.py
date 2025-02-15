import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Any, List, Optional

import click

from .middlewares import Middlewares

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)


def find_python_files(directory: str = ".") -> List[Path]:
    """Find all Python files in the given directory."""
    return list(Path(directory).glob("*.py"))


def execute_python_script(script_path: str, input_data: dict) -> Any:
    """Execute the Python script with the given input."""
    try:
        # Load the module
        spec = importlib.util.spec_from_file_location("dynamic_module", script_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not load spec for {script_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Look for main function
        for func_name in ["main", "run", "execute"]:
            if hasattr(module, func_name):
                main_func = getattr(module, func_name)
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
def run(input: str, entrypoint: Optional[str] = None):
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

        if hasattr(result, "dict"):
            serialized_result = result.dict()
        elif hasattr(result, "to_dict"):
            serialized_result = result.to_dict()
        else:
            serialized_result = (
                dict(result) if isinstance(result, dict) else {"result": result}
            )

        print(json.dumps(serialized_result))

    except FileNotFoundError:
        click.echo(f"Script not found: {entrypoint}")
    except Exception as e:
        click.echo(f"Error: {str(e)}")
