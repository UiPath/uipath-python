import copy
import json
from typing import Any, Dict

from .._models import EvaluationResult
from .._models._evaluators import ScoreType
from ._evaluator_base import EvaluatorBase


class DeterministicEvaluator(EvaluatorBase):
    """Evaluator for deterministic/rule-based evaluations."""

    def __init__(self, target_output_key: str = "*"):
        """Initialize the deterministic evaluator.

        Args:
            target_output_key: Key in output to evaluate ("*" for entire output)
        """
        super().__init__()
        self.target_output_key = target_output_key

    async def evaluate(
        self,
        evaluation_id: str,
        evaluation_name: str,
        input_data: Dict[str, Any],
        expected_output: Dict[str, Any],
        actual_output: Dict[str, Any],
    ) -> EvaluationResult:
        original_actual_output = copy.deepcopy(actual_output)
        original_expected_output = copy.deepcopy(expected_output)

        if self.target_output_key != "*":
            if (
                self.target_output_key not in actual_output
                or self.target_output_key not in expected_output
            ):
                raise ValueError(
                    f"Actual value field '{self.target_output_key}' is missing from the actual or expected output"
                )
            actual_output = actual_output[self.target_output_key]
            expected_output = expected_output[self.target_output_key]

        actual_str = self._canonical_json(actual_output)
        expected_str = self._canonical_json(expected_output)

        are_equal = expected_str == actual_str
        return EvaluationResult(
            evaluation_id=evaluation_id,
            evaluation_name=evaluation_name,
            evaluator_id=self.id,
            evaluator_name=self.name,
            score=are_equal,
            input=input_data,
            expected_output=original_expected_output,
            actual_output=original_actual_output,
            score_type=ScoreType.BOOLEAN,
        )

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
            # Normalize all numbers to float
            return float(obj)
        return obj
