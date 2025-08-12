import copy
import math
from typing import Any, Dict, Tuple

from uipath._cli._evals._evaluators._deterministic_evaluator_base import (
    DeterministicEvaluatorBase,
)
from uipath._cli._evals._models import EvaluationResult
from uipath._cli._evals._models._evaluators import ScoreType


class JsonSimilarityEvaluator(DeterministicEvaluatorBase):
    """Deterministic evaluator that scores structural JSON similarity.

    Compares expected versus actual JSON-like structures and returns a
    numerical score in the range [0, 100]. The comparison is token-based
    and tolerant for numbers and strings (via Levenshtein distance).
    """

    async def evaluate(
        self,
        evaluation_id: str,
        evaluation_name: str,
        input_data: Dict[str, Any],
        expected_output: Dict[str, Any],
        actual_output: Dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate similarity between expected and actual JSON outputs.

        Args:
            evaluation_id: Unique identifier for this evaluation run.
            evaluation_name: Human friendly evaluation name.
            input_data: Input payload used to produce the outputs.
            expected_output: Ground-truth JSON structure.
            actual_output: Produced JSON structure to compare against the ground truth.

        Returns:
            EvaluationResult: Structured result with the numerical similarity score.
        """
        actual_output_copy = copy.deepcopy(actual_output)
        expected_output_copy = copy.deepcopy(expected_output)

        actual_output, expected_output = self._select_targets(
            expected_output, actual_output
        )
        similarity = self._compare_json(expected_output, actual_output)

        return EvaluationResult(
            evaluation_id=evaluation_id,
            evaluation_name=evaluation_name,
            evaluator_id=self.id,
            evaluator_name=self.name,
            score=similarity,
            input=input_data,
            expected_output=expected_output_copy,
            actual_output=actual_output_copy,
            score_type=ScoreType.NUMERICAL,
        )

    def _compare_json(self, expected: Any, actual: Any) -> float:
        matched_leaves, total_leaves = self._compare_tokens(expected, actual)
        if total_leaves == 0:
            return 100.0
        sim = (matched_leaves / total_leaves) * 100.0
        return max(0.0, min(100.0, sim))

    def _compare_tokens(
        self, expected_token: Any, actual_token: Any
    ) -> Tuple[float, float]:
        if self._is_number(expected_token) and self._is_number(actual_token):
            return self._compare_numbers(float(expected_token), float(actual_token))

        if type(expected_token) is not type(actual_token):
            return 0.0, self._count_leaves(expected_token)

        if isinstance(expected_token, dict):
            matched_leaves = total_leaves = 0.0
            # Only expected keys count
            for expected_key, expected_value in expected_token.items():
                if isinstance(actual_token, dict) and expected_key in actual_token:
                    matched, total = self._compare_tokens(
                        expected_value, actual_token[expected_key]
                    )
                else:
                    matched, total = (0.0, self._count_leaves(expected_value))
                matched_leaves += matched
                total_leaves += total
            return matched_leaves, total_leaves

        if isinstance(expected_token, list):
            matched_leaves = total_leaves = 0.0
            common_length = min(len(expected_token), len(actual_token))
            for index in range(common_length):
                matched, total = self._compare_tokens(
                    expected_token[index], actual_token[index]
                )
                matched_leaves += matched
                total_leaves += total
            for index in range(common_length, len(expected_token)):
                total_leaves += self._count_leaves(expected_token[index])
            return (matched_leaves, total_leaves)

        if isinstance(expected_token, bool):
            return (1.0, 1.0) if expected_token == actual_token else (0.0, 1.0)

        if isinstance(expected_token, str):
            return self._compare_strings(expected_token, actual_token)

        return (1.0, 1.0) if str(expected_token) == str(actual_token) else (0.0, 1.0)

    def _compare_numbers(
        self, expected_number: float, actual_number: float
    ) -> Tuple[float, float]:
        total = 1.0
        if math.isclose(expected_number, 0.0, abs_tol=1e-12):
            matched = 1.0 if math.isclose(actual_number, 0.0, abs_tol=1e-12) else 0.0
        else:
            ratio = abs(expected_number - actual_number) / abs(expected_number)
            matched = max(0.0, min(1.0, 1.0 - ratio))
        return matched, total

    def _compare_strings(
        self, expected_string: str, actual_string: str
    ) -> Tuple[float, float]:
        total = 1.0
        if not expected_string and not actual_string:
            return 1.0, total
        distance = self._levenshtein(expected_string, actual_string)
        max_length = max(len(expected_string), len(actual_string))
        similarity = 1.0 - (distance / max_length) if max_length else 1.0
        similarity = max(0.0, min(1.0, similarity))
        return similarity, total

    def _count_leaves(self, token_node: Any) -> float:
        if isinstance(token_node, dict):
            return sum(
                self._count_leaves(child_value) for child_value in token_node.values()
            )
        if isinstance(token_node, list):
            return sum(self._count_leaves(child_value) for child_value in token_node)
        return 1.0

    def _levenshtein(self, source_text: str, target_text: str) -> int:
        if not source_text:
            return len(target_text)
        if not target_text:
            return len(source_text)
        source_len, target_len = len(source_text), len(target_text)
        distance_matrix = [[0] * (target_len + 1) for _ in range(source_len + 1)]
        for row_idx in range(source_len + 1):
            distance_matrix[row_idx][0] = row_idx
        for col_idx in range(target_len + 1):
            distance_matrix[0][col_idx] = col_idx
        for row_idx in range(1, source_len + 1):
            for col_idx in range(1, target_len + 1):
                substitution_cost = (
                    0 if source_text[row_idx - 1] == target_text[col_idx - 1] else 1
                )
                distance_matrix[row_idx][col_idx] = min(
                    distance_matrix[row_idx - 1][col_idx] + 1,  # deletion
                    distance_matrix[row_idx][col_idx - 1] + 1,  # insertion
                    distance_matrix[row_idx - 1][col_idx - 1]
                    + substitution_cost,  # substitution
                )
        return distance_matrix[source_len][target_len]

    def _is_number(self, value: Any) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
