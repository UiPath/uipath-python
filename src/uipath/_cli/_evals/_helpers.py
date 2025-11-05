# type: ignore
import ast
import importlib.util
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Optional

import click

from uipath._cli._utils._console import ConsoleLogger
from uipath._cli._utils._constants import EVALS_DIRECTORY_NAME
from uipath._utils.constants import CUSTOM_EVALUATOR_PREFIX

logger = logging.getLogger(__name__)
console = ConsoleLogger().get_instance()


def try_extract_file_and_class_name(text: str) -> tuple[bool, str, str]:
    if text.startswith(CUSTOM_EVALUATOR_PREFIX):
        file_and_class = text[len(CUSTOM_EVALUATOR_PREFIX) :]
        if ":" not in file_and_class:
            raise ValueError(
                f"evaluatorSchema must include class name after ':' - got: {text}"
            )
        file_path_str, class_name = file_and_class.rsplit(":", 1)

        return True, file_path_str, class_name
    return False, "", ""


def to_kebab_case(text: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", text).lower()


def find_evaluator_file(filename: str) -> Optional[Path]:
    """Find the evaluator file in evals/evaluators/custom folder."""
    custom_evaluators_path = Path.cwd() / EVALS_DIRECTORY_NAME / "evaluators" / "custom"

    if not custom_evaluators_path.exists():
        return None

    file_path = custom_evaluators_path / filename
    if file_path.exists():
        return file_path

    return None


def find_base_evaluator_class(file_path: Path) -> Optional[str]:
    """Parse the Python file and find the class that inherits from BaseEvaluator."""
    try:
        with open(file_path, "r") as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "BaseEvaluator":
                        return node.name
                    elif isinstance(base, ast.Subscript):
                        if (
                            isinstance(base.value, ast.Name)
                            and base.value.id == "BaseEvaluator"
                        ):
                            return node.name

        return None
    except Exception as e:
        logger.error(f"Error parsing file: {e}")
        return None


def load_evaluator_class(file_path: Path, class_name: str) -> Optional[type]:
    """Dynamically load the evaluator class from the file."""
    try:
        parent_dir = str(file_path.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        spec = importlib.util.spec_from_file_location("custom_evaluator", file_path)
        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, class_name):
            return getattr(module, class_name)

        return None
    except Exception as e:
        logger.error(f"Error loading class: {e}")
        return None
    finally:
        # Remove from sys.path
        if parent_dir in sys.path:
            sys.path.remove(parent_dir)


def generate_evaluator_config(evaluator_class: type, class_name: str) -> dict[str, Any]:
    """Generate the evaluator config from the class."""
    try:
        config_type = evaluator_class._extract_config_type()
        config_instance = config_type()
        config_dict = config_instance.model_dump(by_alias=True, exclude_none=False)

        return config_dict
    except Exception as e:
        console.error(f"Error inferring evaluator config: {e}")


def register_evaluator(filename: str) -> tuple[str, str]:
    """Infers the schema and types of a custom evaluator.

    Returns:
        tuple[str, str]:
            - The first string is the path to the python evaluator file.
            - The second string is the evaluator type that corresponds to the schema file.
    """
    if not filename.endswith(".py"):
        filename = filename + ".py"
    file_path = find_evaluator_file(filename)
    if file_path is None:
        console.error(f"Could not find '{filename}' in evals/evaluators/custom folder")

    relative_path = f"evals/evaluators/custom/{filename}"
    console.info(
        f"Found custom evaluator file: {click.style(relative_path, fg='cyan')}"
    )

    class_name = find_base_evaluator_class(file_path)
    if class_name is None:
        console.error(
            f"Could not find a class inheriting from BaseEvaluator in {filename}"
        )

    console.info(f"Found custom evaluator class: {click.style(class_name, fg='cyan')}")

    evaluator_class = load_evaluator_class(file_path, class_name)
    if evaluator_class is None:
        console.error(f"Could not load class {class_name} from {filename}")

    try:
        evaluator_id = evaluator_class.get_evaluator_id()
    except Exception as e:
        console.error(f"Error getting evaluator ID: {e}")

    evaluator_config = generate_evaluator_config(evaluator_class, class_name)
    evaluator_json_type = evaluator_class.generate_json_type()

    evaluators_dir = Path.cwd() / EVALS_DIRECTORY_NAME / "evaluators"
    evaluators_dir.mkdir(parents=True, exist_ok=True)

    evaluator_types_dir = evaluators_dir / "custom" / "types"
    evaluator_types_dir.mkdir(parents=True, exist_ok=True)

    kebab_class_name = to_kebab_case(class_name)
    output_file_evaluator_types = kebab_class_name + "-types.json"
    evaluator_types_output_path = (
        evaluators_dir / "custom" / "types" / output_file_evaluator_types
    )

    with open(evaluator_types_output_path, "w") as f:
        json.dump(evaluator_json_type, f, indent=2)

    relative_output_path = (
        f"evals/evaluators/custom/types/{output_file_evaluator_types}"
    )
    console.success(
        f"Generated evaluator types: {click.style(relative_output_path, fg='cyan')}"
    )

    output = {
        "version": "1.0",
        "id": evaluator_id,
        "evaluatorTypeId": f"{CUSTOM_EVALUATOR_PREFIX}types/{output_file_evaluator_types}",
        "evaluatorSchema": f"{CUSTOM_EVALUATOR_PREFIX}{filename}:{class_name}",
        "description": evaluator_class.__doc__,
        "evaluatorConfig": evaluator_config,
    }

    output_file_evaluator_spec = kebab_class_name + ".json"
    evaluator_spec_output_path = evaluators_dir / output_file_evaluator_spec
    with open(evaluator_spec_output_path, "w") as f:
        json.dump(output, f, indent=2)

    relative_output_path = f"evals/evaluators/{output_file_evaluator_spec}"
    console.success(
        f"Generated evaluator spec: {click.style(relative_output_path, fg='cyan')}"
    )

    return str(file_path), str(evaluator_types_output_path)
