"""LLM judge trajectory evaluator for evaluating agent execution trajectories."""

from typing import Any, TypeVar

from pydantic import BaseModel

from .._helpers.evaluators_helpers import trace_to_str
from ..models import (
    AgentExecution,
    EvaluationResult,
    EvaluatorType,
)
from ..models.llm_judge_types import (
    LLMJudgePromptTemplates,
    LLMJudgeTrajectoryOutputSchema,
)
from .base_evaluator import BaseEvaluationCriteria
from .llm_as_judge_evaluator import (
    BaseLLMJudgeEvaluatorConfig,
    LLMJudgeMixin,
)


class TrajectoryEvaluationCriteria(BaseEvaluationCriteria):
    """Evaluation criteria for trajectory-based evaluations."""

    expected_agent_behavior: str


class LLMJudgeTrajectoryEvaluatorConfig(
    BaseLLMJudgeEvaluatorConfig[TrajectoryEvaluationCriteria]
):
    """Configuration for the llm judge trajectory evaluator."""

    name: str = "LLMJudgeTrajectoryEvaluator"
    prompt: str = LLMJudgePromptTemplates.LLM_JUDGE_TRAJECTORY_DEFAULT_USER_PROMPT


class LLMJudgeTrajectorySimulationEvaluatorConfig(
    BaseLLMJudgeEvaluatorConfig[TrajectoryEvaluationCriteria]
):
    """Configuration for the llm judge simulation trajectory evaluator."""

    name: str = "LLMJudgeTrajectorySimulationEvaluator"
    prompt: str = (
        LLMJudgePromptTemplates.LLM_JUDGE_SIMULATION_TRAJECTORY_DEFAULT_USER_PROMPT
    )


TC = TypeVar("TC", bound=BaseLLMJudgeEvaluatorConfig[TrajectoryEvaluationCriteria])


class BaseLLMTrajectoryEvaluator(LLMJudgeMixin[TrajectoryEvaluationCriteria, TC]):
    """Base class for LLM trajectory evaluators that contains all shared functionality.

    This class encapsulates the common evaluation logic for trajectory-based LLM evaluators,
    including output extraction, prompt formatting, and evaluation criteria handling.
    """

    output_schema: type[BaseModel] = LLMJudgeTrajectoryOutputSchema
    actual_output_placeholder: str = "{{AgentRunHistory}}"
    expected_output_placeholder: str = "{{ExpectedAgentBehavior}}"
    user_input_placeholder: str = "{{UserOrSyntheticInput}}"
    simulation_instructions_placeholder: str = "{{SimulationInstructions}}"

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.LLM_JUDGE_TRAJECTORY.value

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: TrajectoryEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate using trajectory analysis."""
        return await super().evaluate(agent_execution, evaluation_criteria)

    def _get_actual_output(self, agent_execution: AgentExecution) -> Any:
        """Get the actual output from the agent execution."""
        return trace_to_str(agent_execution.agent_trace)

    def _get_expected_output(
        self, evaluation_criteria: TrajectoryEvaluationCriteria
    ) -> Any:
        """Get the expected agent behavior from the evaluation criteria."""
        return evaluation_criteria.expected_agent_behavior

    def _create_evaluation_prompt(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: TrajectoryEvaluationCriteria,
    ) -> str:
        """Create the evaluation prompt for the LLM."""
        formatted_prompt = super()._create_evaluation_prompt(
            agent_execution, evaluation_criteria
        )
        formatted_prompt = formatted_prompt.replace(
            self.user_input_placeholder,
            str(agent_execution.agent_input),
        )
        formatted_prompt = formatted_prompt.replace(
            self.simulation_instructions_placeholder,
            agent_execution.simulation_instructions,
        )
        return formatted_prompt


class LLMJudgeTrajectoryEvaluator(
    BaseLLMTrajectoryEvaluator[LLMJudgeTrajectoryEvaluatorConfig]
):
    """Evaluator that uses an LLM to judge the quality of agent trajectory.

    Inherits all functionality from BaseLLMTrajectoryEvaluator but uses the standard
    system prompt and configuration for general trajectory evaluation.
    """

    system_prompt: str = LLMJudgePromptTemplates.LLM_JUDGE_TRAJECTORY_SYSTEM_PROMPT

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.LLM_JUDGE_TRAJECTORY_SIMILARITY.value


class LLMJudgeTrajectorySimulationEvaluator(
    BaseLLMTrajectoryEvaluator[LLMJudgeTrajectorySimulationEvaluatorConfig]
):
    """Evaluator that uses an LLM to judge the quality of agent trajectory for simulations.

    Inherits all functionality from BaseLLMTrajectoryEvaluator but uses a different system prompt
    and configuration specific to simulation evaluation.
    """

    system_prompt: str = (
        LLMJudgePromptTemplates.LLM_JUDGE_SIMULATION_TRAJECTORY_SYSTEM_PROMPT
    )

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.LLM_JUDGE_TRAJECTORY_SIMULATION.value
