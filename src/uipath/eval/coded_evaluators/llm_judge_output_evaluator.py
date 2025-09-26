"""LLM judge output evaluators for evaluating agent outputs."""

from pydantic import BaseModel

from ..models import AgentExecution, EvaluationResult
from ..models.llm_judge_types import (
    LLMJudgeOutputSchema,
    LLMJudgePromptTemplates,
    LLMJudgeStrictJSONSimilarityOutputSchema,
)
from .llm_as_judge_evaluator import (
    BaseLLMJudgeEvaluatorConfig,
    LLMJudgeMixin,
)
from .output_evaluator import (
    OutputEvaluationCriteria,
    OutputEvaluator,
    OutputEvaluatorConfig,
)


class LLMJudgeOutputEvaluatorConfig(OutputEvaluatorConfig, BaseLLMJudgeEvaluatorConfig):
    """Configuration for the LLM judge output evaluator."""

    name: str = "LLMJudgeOutputEvaluator"
    prompt: str = LLMJudgePromptTemplates.LLM_JUDGE_DEFAULT_USER_PROMPT


class LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig(LLMJudgeOutputEvaluatorConfig):
    """Configuration for the LLM judge strict JSON similarity output evaluator."""

    name: str = "LLMJudgeStrictJSONSimilarityOutputEvaluator"
    prompt: str = (
        LLMJudgePromptTemplates.LLM_JUDGE_STRICT_JSON_SIMILARITY_DEFAULT_USER_PROMPT
    )


class LLMJudgeOutputEvaluator(
    OutputEvaluator[LLMJudgeOutputEvaluatorConfig],
    LLMJudgeMixin[OutputEvaluationCriteria, LLMJudgeOutputEvaluatorConfig],
):
    """Evaluator that uses an LLM to judge the quality of agent output.

    Inherits from both LLMJudgeMixin (for LLM functionality) and OutputEvaluator
    (for output-specific methods like _get_actual_output and _get_expected_output).
    """

    system_prompt: str = LLMJudgePromptTemplates.LLM_JUDGE_SYSTEM_PROMPT
    output_schema: type[BaseModel] = LLMJudgeOutputSchema

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: OutputEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate using an LLM as a judge."""
        # Explicitly delegate to LLMJudgeMixin's evaluate method to override BaseEvaluator
        return await LLMJudgeMixin.evaluate(self, agent_execution, evaluation_criteria)


class LLMJudgeStrictJSONSimilarityOutputEvaluator(
    OutputEvaluator[LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig],
    LLMJudgeMixin[
        OutputEvaluationCriteria, LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig
    ],
):
    """Evaluator that uses an LLM to judge the quality of agent output with strict JSON similarity."""

    system_prompt: str = (
        LLMJudgePromptTemplates.LLM_JUDGE_STRICT_JSON_SIMILARITY_SYSTEM_PROMPT
    )
    output_schema: type[BaseModel] = LLMJudgeStrictJSONSimilarityOutputSchema

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: OutputEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate using an LLM as a judge with strict JSON similarity."""
        # Explicitly delegate to LLMJudgeMixin's evaluate method to override BaseEvaluator
        return await LLMJudgeMixin.evaluate(self, agent_execution, evaluation_criteria)
