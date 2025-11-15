import logging
import os
import re
from pathlib import Path
from string import Template

import click

from ._utils._console import ConsoleLogger
from ._utils._constants import EVALS_DIRECTORY_NAME
from ._utils._resources import Resources

logger = logging.getLogger(__name__)
console = ConsoleLogger()


def to_pascal_case(text: str) -> str:
    """Convert kebab-case or snake_case to PascalCase."""
    return "".join(word.capitalize() for word in re.sub(r"[-_]", " ", text).split())


def to_snake_case(text: str) -> str:
    """Convert kebab-case or PascalCase to snake_case."""
    return re.sub(r"(?<!^)(?=[A-Z])|-", "_", text).lower()


def generate_evaluator_template(evaluator_name: str) -> str:
    """Generate a generic evaluator template."""
    class_name = to_pascal_case(evaluator_name)
    if not class_name.endswith("Evaluator"):
        class_name = class_name + "Evaluator"

    variables = {
        "class_name": class_name,
        "evaluator_name": evaluator_name,
        "criteria_class": class_name.replace("Evaluator", "EvaluationCriteria"),
        "config_class": class_name + "Config",
    }
    templates_path = os.path.join(
        os.path.dirname(__file__), "_templates", "custom_evaluator.py.template"
    )
    with open(templates_path, "r", encoding="utf-8-sig") as f:
        content = f.read()

    return Template(content).substitute(variables)


def create_evaluator(evaluator_name):
    cwd = Path.cwd()
    custom_evaluators_dir = cwd / EVALS_DIRECTORY_NAME / "evaluators" / "custom"

    if not custom_evaluators_dir.exists():
        console.info(
            f"Creating {click.style('evals/evaluators/custom', fg='cyan')} folder"
        )
        custom_evaluators_dir.mkdir(parents=True, exist_ok=True)

    filename = to_snake_case(evaluator_name)
    if not filename.endswith(".py"):
        filename = filename + ".py"

    file_path = custom_evaluators_dir / filename

    if file_path.exists():
        console.error(f"Evaluator file already exists: {file_path}")

    template_content = generate_evaluator_template(evaluator_name)

    with open(file_path, "w") as f:
        f.write(template_content)

    relative_path = f"evals/evaluators/custom/{filename}"

    console.success(f"Created new evaluator: {click.style(relative_path, fg='cyan')}")
    console.hint("Next steps:")
    console.hint(
        f"  1. Edit {click.style(relative_path, fg='cyan')} to implement your evaluation logic"
    )
    console.hint(
        f"  2. Run {click.style(f'uipath register evaluator {filename}', fg='cyan')} to generate the evaluator spec"
    )


@click.command()
@click.argument("resource", required=True)
@click.argument("args", nargs=-1)
def add(resource: str, args: tuple[str]) -> None:
    """Create a local resource.

    Examples:
        uipath add evaluator my-custom-evaluator
    """
    match Resources.from_string(resource):
        case Resources.EVALUATOR:
            usage_hint = f"Usage: {click.style('uipath add evaluator <evaluator_name>', fg='cyan')}"
            if len(args) < 1:
                console.hint(usage_hint)
                console.error("Missing required argument: evaluator_name")
                return
            if len(args) > 1:
                console.hint(usage_hint)
                console.error(
                    f"Too many arguments provided: {args}. Expected only evaluator_name."
                )

            evaluator_name = args[0]

            if not isinstance(evaluator_name, str) or not evaluator_name.strip():
                console.hint(usage_hint)
                console.error("Invalid evaluator_name: must be a non-empty string")
                return

            create_evaluator(evaluator_name)
