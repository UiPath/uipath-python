"""Generate the JSON types for all evaluators."""

import json
import os
from typing import Any

from uipath.eval.evaluators import EVALUATORS


def generate_evaluator_json_types(
    write_to_file: bool = False, indent: int | str | None = None
) -> dict[str, Any]:
    """Generate the JSON types for all evaluators."""
    OUTPUT_PATH = os.path.dirname(os.path.abspath(__file__))

    os.makedirs(OUTPUT_PATH, exist_ok=True)

    evaluator_json_types = {}
    for evaluator in EVALUATORS:
        evaluator_json_type = evaluator.generate_json_type()
        evaluator_json_types[evaluator.__name__] = evaluator_json_type
        if write_to_file:
            with open(
                os.path.join(OUTPUT_PATH, f"{evaluator.__name__}.json"), "w"
            ) as f:
                json.dump(evaluator_json_type, f, indent=indent)
    return evaluator_json_types


if __name__ == "__main__":
    generate_evaluator_json_types(write_to_file=True, indent=2)
