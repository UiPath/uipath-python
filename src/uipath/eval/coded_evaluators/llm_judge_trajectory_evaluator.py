"""LLM judge trajectory evaluator for evaluating agent execution trajectories."""

from typing import Any

from pydantic import BaseModel, Field

from .._helpers.helpers import trace_to_str
from ..models import (
    AgentExecution,
)
from ..models.llm_judge_types import (
    LLMJudgePromptTemplates,
    LLMJudgeTrajectoryOutputSchema,
)
from .llm_as_judge_evaluator import (
    BaseLLMJudgeEvaluator,
    LLMJudgeEvaluatorConfig,
)
from .output_evaluator import (
    OutputEvaluationCriteria,
)


class LLMJudgeTrajectoryEvaluatorConfig(LLMJudgeEvaluatorConfig):
    """Configuration for the llm judge trajectory evaluator."""

    name: str = "LlmJudgeTrajectoryEvaluator"
    prompt: str = LLMJudgePromptTemplates.LLM_JUDGE_TRAJECTORY_DEFAULT_USER_PROMPT
    target_output_key: str = Field(default="*", frozen=True)


class LLMJudgeSimulationEvaluatorConfig(LLMJudgeEvaluatorConfig):
    """Configuration for the llm judge simulation trajectory evaluator."""

    name: str = "LlmJudgeSimulationEvaluator"
    prompt: str = (
        LLMJudgePromptTemplates.LLM_JUDGE_SIMULATION_TRAJECTORY_DEFAULT_USER_PROMPT
    )


class LLMJudgeTrajectoryEvaluator(
    BaseLLMJudgeEvaluator[LLMJudgeTrajectoryEvaluatorConfig]
):
    """Evaluator that uses an LLM to judge the quality of agent trajectory."""

    system_prompt: str = LLMJudgePromptTemplates.LLM_JUDGE_TRAJECTORY_SYSTEM_PROMPT
    output_schema: type[BaseModel] = LLMJudgeTrajectoryOutputSchema
    actual_output_placeholder: str = "{{AgentRunHistory}}"
    expected_output_placeholder: str = "{{ExpectedAgentBehavior}}"
    user_input_placeholder: str = "{{UserOrSyntheticInput}}"
    simulation_instructions_placeholder: str = "{{SimulationInstructions}}"

    def _get_actual_output(self, agent_execution: AgentExecution) -> Any:
        """Get the actual output from the agent execution."""
        return trace_to_str(agent_execution.agent_trace)

    def _create_evaluation_prompt(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: OutputEvaluationCriteria,
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


class LlmJudgeSimulationTrajectoryEvaluator(
    BaseLLMJudgeEvaluator[LLMJudgeSimulationEvaluatorConfig]
):
    """Evaluator that uses an LLM to judge the quality of agent trajectory."""

    system_prompt: str = (
        LLMJudgePromptTemplates.LLM_JUDGE_SIMULATION_TRAJECTORY_SYSTEM_PROMPT
    )
