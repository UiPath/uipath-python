"""JSON similarity evaluator for flexible structural comparison of outputs."""

import math
from typing import Any, Tuple

from ..models import (
    AgentExecution,
    EvaluationResult,
    EvaluatorType,
    NumericEvaluationResult,
)
from .output_evaluator import (
    OutputEvaluationCriteria,
    OutputEvaluator,
    OutputEvaluatorConfig,
)


class JsonSimilarityEvaluatorConfig(OutputEvaluatorConfig[OutputEvaluationCriteria]):
    """Configuration for the json similarity evaluator."""

    name: str = "JsonSimilarityEvaluator"


class JsonSimilarityEvaluator(
    OutputEvaluator[OutputEvaluationCriteria, JsonSimilarityEvaluatorConfig, str]
):
    """Deterministic evaluator that scores structural JSON similarity between expected and actual output.

    Compares expected versus actual JSON-like structures and returns a
    numerical score in the range [0, 100]. The comparison is token-based
    and tolerant for numbers and strings (via Levenshtein distance).
    """

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.JSON_SIMILARITY.value

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: OutputEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate similarity between expected and actual JSON outputs.

        Uses token-based comparison with tolerance for numeric differences
        and Levenshtein distance for string similarity.

            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - actual_output: The actual output from the agent
                - spans: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate

        Returns:
            EvaluationResult: Numerical score between 0-100 indicating similarity
        """
        score, justification = self._compare_json(
            self._get_expected_output(evaluation_criteria),
            self._get_actual_output(agent_execution),
        )
        validated_justification = self.validate_justification(justification)
        return NumericEvaluationResult(
            score=score,
            details=validated_justification,
        )

    def _compare_json(self, expected: Any, actual: Any) -> tuple[float, str]:
        matched_leaves, total_leaves = self._compare_tokens(expected, actual)
        if total_leaves == 0:
            return 1.0, "Total leaves are 0"
        sim = matched_leaves / total_leaves
        return (
            max(0.0, min(1.0, sim)),
            f"Matched leaves: {matched_leaves}, Total leaves: {total_leaves}",
        )

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
