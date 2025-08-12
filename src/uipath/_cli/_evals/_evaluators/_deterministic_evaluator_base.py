import copy
import json
from abc import ABC
from typing import Any, Dict, Tuple

from ._evaluator_base import EvaluatorBase


class DeterministicEvaluatorBase(EvaluatorBase, ABC):
    def __init__(self, target_output_key: str = "*"):
        super().__init__()
        self.target_output_key = target_output_key

    def _select_targets(
        self, expected_output: Dict[str, Any], actual_output: Dict[str, Any]
    ) -> Tuple[Any, Any]:
        actual_output_copy = copy.deepcopy(actual_output)
        expected_output_copy = copy.deepcopy(expected_output)
        if self.target_output_key != "*":
            if (
                self.target_output_key not in actual_output
                or self.target_output_key not in expected_output
            ):
                raise ValueError(
                    f"Field '{self.target_output_key}' missing from expected or actual output"
                )
            actual_output_copy = actual_output_copy[self.target_output_key]
            expected_output_copy = expected_output[self.target_output_key]
        return actual_output_copy, expected_output_copy

    def _canonical_json(self, obj: Any) -> str:
        return json.dumps(
            self._normalize_numbers(obj),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def _normalize_numbers(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._normalize_numbers(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._normalize_numbers(v) for v in obj]
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            return float(obj)
        return obj
