"""Contains evaluator for agent outputs."""

from .._helpers.coded_evaluators_helpers import generate_datapoint_id
from ..models import AgentExecution, EvaluationResult, NumericEvaluationResult
from .base_evaluator import BaseEvaluationCriteria, BaseEvaluator, BaseEvaluatorConfig


class ContainsEvaluationCriteria(BaseEvaluationCriteria):
    """Evaluation criteria for the contains evaluator."""

    search_text: str


class ContainsEvaluatorConfig(BaseEvaluatorConfig[ContainsEvaluationCriteria]):
    """Configuration for the contains evaluator."""

    name: str = "ContainsEvaluator"
    case_sensitive: bool = False
    negated: bool = False


class ContainsEvaluator(
    BaseEvaluator[ContainsEvaluationCriteria, ContainsEvaluatorConfig, type(None)]
):
    """Evaluator that checks if the actual output contains the expected output.

    This evaluator returns True if the actual output contains the expected output,
    and False otherwise. It supports case sensitivity and negation options.
    """

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return "uipath-contains"

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: ContainsEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate whether actual output contains the expected output.

        Args:
            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - agent_output: The actual output from the agent
                - agent_trace: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate

        Returns:
            EvaluationResult: Boolean result indicating if output contains expected value (True/False)
        """
        actual_output = str(self._get_actual_output(agent_execution))
        expected_output = str(self._get_expected_output(evaluation_criteria))

        if not self.evaluator_config.case_sensitive:
            actual_output = actual_output.lower()
            expected_output = expected_output.lower()

        is_contains = expected_output in actual_output

        if self.evaluator_config.negated:
            is_contains = not is_contains

        return NumericEvaluationResult(
            score=float(is_contains),
            evaluator_name=self.evaluator_config.name,
            datapoint_id=generate_datapoint_id(agent_execution),
        )

    def _get_actual_output(self, agent_execution: AgentExecution) -> str:
        """Get the actual output from the agent execution."""
        return str(agent_execution.agent_output)

    def _get_expected_output(
        self, evaluation_criteria: ContainsEvaluationCriteria
    ) -> str:
        """Get the expected output from the evaluation criteria."""
        return evaluation_criteria.search_text
