import copy
from typing import Any, Dict

from uipath._cli._evals._evaluators._deterministic_evaluator_base import (
    DeterministicEvaluatorBase,
)
from uipath._cli._evals._models import EvaluationResult
from uipath._cli._evals._models._evaluators import ScoreType


class ExactMatchEvaluator(DeterministicEvaluatorBase):
    async def evaluate(
        self,
        evaluation_id: str,
        evaluation_name: str,
        input_data: Dict[str, Any],
        expected_output: Dict[str, Any],
        actual_output: Dict[str, Any],
    ) -> EvaluationResult:
        actual_output_copy = copy.deepcopy(actual_output)
        expected_output_copy = copy.deepcopy(expected_output)

        actual_output, expected_output = self._select_targets(
            expected_output, actual_output
        )
        are_equal = self._canonical_json(actual_output) == self._canonical_json(
            expected_output
        )

        return EvaluationResult(
            evaluation_id=evaluation_id,
            evaluation_name=evaluation_name,
            evaluator_id=self.id,
            evaluator_name=self.name,
            score=are_equal,
            input=input_data,
            expected_output=expected_output_copy,
            actual_output=actual_output_copy,
            score_type=ScoreType.BOOLEAN,
        )
