"""UiPath platform extension of BaseLegacyEvaluator.

Adds line-by-line evaluation and job attachment URI support on top of the
canonical uipath_eval.BaseLegacyEvaluator so all legacy evaluators form a
single class hierarchy.
"""

from typing import Any, Generic, TypeVar

from pydantic import Field

# Re-export so importers of this module get everything they need
from uipath_eval.evaluators.base_evaluator import (  # noqa: F401
    BaseEvaluationCriteria,
    BaseEvaluatorConfig,
    GenericBaseEvaluator,
)
from uipath_eval.evaluators.base_legacy_evaluator import (
    BaseLegacyEvaluator as _BaseLegacyEvaluator,
)
from uipath_eval.evaluators.base_legacy_evaluator import (
    LegacyEvaluationCriteria,
    LegacyEvaluatorConfig,
    track_evaluation_metrics,
)
from uipath_eval.models.models import AgentExecution

from ..models import EvaluationResult
from .attachment_utils import (
    download_attachment_as_string,
    extract_attachment_id,
    is_job_attachment_uri,
)
from .line_by_line_utils import split_into_lines

T = TypeVar("T", bound=LegacyEvaluatorConfig)


class BaseLegacyEvaluator(_BaseLegacyEvaluator[T], Generic[T]):
    """UiPath-platform extension of the canonical BaseLegacyEvaluator.

    Adds:
    - Line-by-line evaluation (``lineByLineEvaluation``)
    - Job attachment URI auto-download in ``_get_actual_output``
    """

    line_by_line_evaluation: bool = Field(default=False, alias="lineByLineEvaluation")
    line_delimiter: str = Field(default="\n", alias="lineDelimiter")

    async def validate_and_evaluate_criteria(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Validate criteria and evaluate, using line-by-line mode if configured."""
        criteria = self.validate_evaluation_criteria(evaluation_criteria)
        if self.line_by_line_evaluation:
            return await self._evaluate_line_by_line(agent_execution, criteria)
        return await self.evaluate(agent_execution, criteria)

    async def _evaluate_line_by_line(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        from .line_by_line_utils import build_line_by_line_result, evaluate_lines

        actual_output = self._get_actual_output(agent_execution)
        expected_output = evaluation_criteria.expected_output

        actual_lines = split_into_lines(
            actual_output, self.line_delimiter, self.target_output_key
        )
        expected_lines = split_into_lines(
            expected_output, self.line_delimiter, self.target_output_key
        )

        def create_line_criteria(expected_line: str) -> LegacyEvaluationCriteria:
            from .line_by_line_utils import wrap_line_in_structure

            line_expected_output = wrap_line_in_structure(
                expected_line, self.target_output_key
            )
            return LegacyEvaluationCriteria(
                expected_output=line_expected_output,
                expected_agent_behavior=evaluation_criteria.expected_agent_behavior,
            )

        line_details, line_results = await evaluate_lines(
            actual_lines=actual_lines,
            expected_lines=expected_lines,
            target_output_key=self.target_output_key,
            agent_execution=agent_execution,
            evaluate_fn=self.evaluate,
            create_line_criteria_fn=create_line_criteria,
        )

        return build_line_by_line_result(
            line_details=line_details,
            line_results=line_results,
            actual_lines=actual_lines,
            expected_lines=expected_lines,
        )

    def _get_actual_output(self, agent_execution: AgentExecution) -> Any:
        agent_output = agent_execution.agent_output

        if self.target_output_key == "*":
            result = agent_output
        elif isinstance(agent_output, dict) and self.target_output_key in agent_output:
            result = agent_output[self.target_output_key]
        else:
            result = agent_output

        if is_job_attachment_uri(result):
            assert isinstance(result, str)
            attachment_id = extract_attachment_id(result)
            result = download_attachment_as_string(attachment_id)

        return result


__all__ = [
    "BaseLegacyEvaluator",
    "LegacyEvaluationCriteria",
    "LegacyEvaluatorConfig",
    "track_evaluation_metrics",
    "BaseEvaluationCriteria",
    "BaseEvaluatorConfig",
    "GenericBaseEvaluator",
]
