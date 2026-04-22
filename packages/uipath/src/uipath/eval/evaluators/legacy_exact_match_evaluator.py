"""Exact match evaluator with line-by-line evaluation support."""

from typing import Any

from pydantic import Field
from uipath_eval.evaluators.base_legacy_evaluator import (
    LegacyEvaluationCriteria,
    LegacyEvaluatorConfig,
)
from uipath_eval.evaluators.legacy_deterministic_evaluator_base import (
    BaseLegacyDeterministicEvaluator,
)

from .._helpers.output_path import resolve_output_path
from ..models.models import AgentExecution, EvaluationResult
from .line_by_line_utils import (
    aggregate_line_scores,
    build_line_by_line_result,
    evaluate_lines,
    split_into_lines,
    wrap_line_in_structure,
)


class LegacyExactMatchEvaluatorConfig(LegacyEvaluatorConfig):
    """Configuration for legacy exact-match evaluators."""

    name: str = "LegacyExactMatchEvaluator"
    line_by_line_evaluation: bool = Field(default=False, alias="lineByLineEvaluation")
    line_delimiter: str = Field(default="\n", alias="lineDelimiter")


class LegacyExactMatchEvaluator(
    BaseLegacyDeterministicEvaluator[LegacyExactMatchEvaluatorConfig]
):
    """Evaluator that performs exact structural matching between expected and actual outputs.

    Supports optional line-by-line mode where the output is split by a delimiter and
    each line is evaluated independently, returning an aggregated numeric score.
    """

    line_by_line_evaluation: bool = Field(default=False, alias="lineByLineEvaluation")
    line_delimiter: str = Field(default="\n", alias="lineDelimiter")

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate whether actual output exactly matches expected output.

        Args:
            agent_execution: The execution details
            evaluation_criteria: The criteria to evaluate

        Returns:
            EvaluationResult: Boolean (plain match) or NumericEvaluationResult (line-by-line)
        """
        if self.line_by_line_evaluation:
            return await self._evaluate_line_by_line(agent_execution, evaluation_criteria)
        return await self._evaluate_exact(agent_execution, evaluation_criteria)

    async def _evaluate_exact(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        from ..models import BooleanEvaluationResult

        actual_output: Any = agent_execution.agent_output
        expected_output: Any = evaluation_criteria.expected_output

        if self.target_output_key and self.target_output_key != "*":
            if isinstance(actual_output, dict) and isinstance(expected_output, dict):
                actual_resolved = True
                expected_resolved = True

                try:
                    actual_output = resolve_output_path(
                        actual_output, self.target_output_key
                    )
                except (KeyError, IndexError, TypeError):
                    actual_resolved = False

                try:
                    expected_output = resolve_output_path(
                        expected_output, self.target_output_key
                    )
                except (KeyError, IndexError, TypeError):
                    expected_resolved = False

                if not actual_resolved or not expected_resolved:
                    actual_output = expected_output = {}

        return BooleanEvaluationResult(
            score=self._canonical_json(actual_output)
            == self._canonical_json(expected_output)
        )

    async def _evaluate_line_by_line(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        actual_lines = split_into_lines(
            agent_execution.agent_output,
            self.line_delimiter,
            self.target_output_key,
        )
        expected_lines = split_into_lines(
            evaluation_criteria.expected_output,
            self.line_delimiter,
            self.target_output_key,
        )

        if not actual_lines and not expected_lines:
            from ..models import BooleanEvaluationResult

            return BooleanEvaluationResult(score=True)

        line_details, line_results = await evaluate_lines(
            actual_lines=actual_lines,
            expected_lines=expected_lines,
            target_output_key=self.target_output_key,
            agent_execution=agent_execution,
            evaluate_fn=self._evaluate_exact,
            create_line_criteria_fn=lambda expected_line: LegacyEvaluationCriteria(
                expectedOutput=wrap_line_in_structure(
                    expected_line, self.target_output_key
                ),
                expectedAgentBehavior="",
            ),
        )

        if not line_results:
            from ..models.models import NumericEvaluationResult

            return NumericEvaluationResult(score=0.0)

        _ = aggregate_line_scores(line_results)
        return build_line_by_line_result(
            line_details=line_details,
            line_results=line_results,
            actual_lines=actual_lines,
            expected_lines=expected_lines,
        )
