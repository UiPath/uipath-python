"""Module for registering custom evaluators in the UiPath evaluation framework."""

import ast
import importlib.util
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

from ..constants import CUSTOM_EVALUATOR_PREFIX, EVALS_FOLDER

logger = logging.getLogger(__name__)


class EvaluatorRegistrationError(Exception):
    """Raised when evaluator registration fails."""

    pass


def to_kebab_case(text: str) -> str:
    """Convert a given string to kebab-case."""
    return re.sub(r"(?<!^)(?=[A-Z])", "-", text).lower()


def find_evaluator_file(filename: str) -> Path | None:
    """Find the evaluator file in evals/evaluators/custom folder."""
    custom_evaluators_path = Path.cwd() / EVALS_FOLDER / "evaluators" / "custom"

    if not custom_evaluators_path.exists():
        return None

    file_path = custom_evaluators_path / filename
    if file_path.exists():
        return file_path

    return None


def find_base_evaluator_class(file_path: Path) -> str | None:
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


def load_evaluator_class(file_path: Path, class_name: str) -> Any | None:
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


def generate_evaluator_config(evaluator_class: Any, class_name: str) -> dict[str, Any]:
    """Generate the evaluator config from the class."""
    try:
        config_type = evaluator_class._extract_config_type()
        config_instance = config_type()
        config_dict = config_instance.model_dump(by_alias=True, exclude_none=False)

        return config_dict
    except Exception as e:
        raise EvaluatorRegistrationError(
            f"Error inferring evaluator config: {e}"
        ) from e


def register_evaluator(filename: str) -> tuple[str, str]:
    """Infers the schema and types of a custom evaluator.

    Returns:
        tuple[str, str]:
            - The first string is the path to the python evaluator file.
            - The second string is the evaluator type that corresponds to the schema file.

    Raises:
        EvaluatorRegistrationError: If registration fails at any step.
    """
    if not filename.endswith(".py"):
        filename = filename + ".py"
    file_path = find_evaluator_file(filename)
    if file_path is None:
        raise EvaluatorRegistrationError(
            f"Could not find '{filename}' in {EVALS_FOLDER}/evaluators/custom folder"
        )

    logger.info(f"Found custom evaluator file: evals/evaluators/custom/{filename}")

    class_name = find_base_evaluator_class(file_path)
    if class_name is None:
        raise EvaluatorRegistrationError(
            f"Could not find a class inheriting from BaseEvaluator in {filename}"
        )

    logger.info(f"Found custom evaluator class: {class_name}")

    evaluator_class = load_evaluator_class(file_path, class_name)
    if evaluator_class is None:
        raise EvaluatorRegistrationError(
            f"Could not load class {class_name} from {filename}"
        )

    try:
        evaluator_id = evaluator_class.get_evaluator_id()
    except Exception as e:
        raise EvaluatorRegistrationError(f"Error getting evaluator ID: {e}") from e

    evaluator_config = generate_evaluator_config(evaluator_class, class_name)
    evaluator_json_type = evaluator_class.generate_json_type()

    evaluators_dir = Path.cwd() / EVALS_FOLDER / "evaluators"
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

    logger.info(
        f"Generated evaluator types: {EVALS_FOLDER}/evaluators/custom/types/{output_file_evaluator_types}"
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

    logger.info(
        f"Generated evaluator spec: evals/evaluators/{output_file_evaluator_spec}"
    )

    return str(file_path), str(evaluator_types_output_path)
