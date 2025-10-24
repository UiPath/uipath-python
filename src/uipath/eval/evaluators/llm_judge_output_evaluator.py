"""LLM judge output evaluators for evaluating agent outputs."""

from typing import TypeVar

from pydantic import BaseModel

from uipath.eval.models import EvaluatorType

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


class BaseLLMJudgeOutputCriteriaEvaluatorConfig(
    OutputEvaluatorConfig[OutputEvaluationCriteria],
    BaseLLMJudgeEvaluatorConfig[OutputEvaluationCriteria],
):
    """Base configuration for LLM judge output criteria evaluators."""

    pass


class LLMJudgeOutputEvaluatorConfig(BaseLLMJudgeOutputCriteriaEvaluatorConfig):
    """Configuration for the LLM judge output evaluator."""

    name: str = "LLMJudgeOutputEvaluator"
    prompt: str = LLMJudgePromptTemplates.LLM_JUDGE_DEFAULT_USER_PROMPT


class LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig(LLMJudgeOutputEvaluatorConfig):
    """Configuration for the LLM judge strict JSON similarity output evaluator."""

    name: str = "LLMJudgeStrictJSONSimilarityOutputEvaluator"
    prompt: str = (
        LLMJudgePromptTemplates.LLM_JUDGE_STRICT_JSON_SIMILARITY_DEFAULT_USER_PROMPT
    )


OC = TypeVar("OC", bound=LLMJudgeOutputEvaluatorConfig)


class BaseLLMOutputEvaluator(
    OutputEvaluator[OutputEvaluationCriteria, OC, str],
    LLMJudgeMixin[OutputEvaluationCriteria, OC],
):
    """Base class for LLM judge output evaluators that contains all shared functionality.

    This class encapsulates the common evaluation logic for output-based LLM evaluators,
    combining OutputEvaluator (for output extraction) with LLMJudgeMixin (for LLM functionality).
    """

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.LLM_JUDGE_OUTPUT.value

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: OutputEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate using an LLM as a judge."""
        # Explicitly delegate to LLMJudgeMixin's evaluate method to override BaseEvaluator
        return await LLMJudgeMixin.evaluate(self, agent_execution, evaluation_criteria)


class LLMJudgeOutputEvaluator(BaseLLMOutputEvaluator[LLMJudgeOutputEvaluatorConfig]):
    """Evaluator that uses an LLM to judge the quality of agent output.

    Inherits all functionality from BaseLLMOutputEvaluator but uses the standard
    system prompt and output schema for general output evaluation.
    """

    system_prompt: str = LLMJudgePromptTemplates.LLM_JUDGE_SYSTEM_PROMPT
    output_schema: type[BaseModel] = LLMJudgeOutputSchema

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.LLM_JUDGE_OUTPUT_SEMANTIC_SIMILARITY.value


class LLMJudgeStrictJSONSimilarityOutputEvaluator(
    BaseLLMOutputEvaluator[LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig]
):
    """Evaluator that uses an LLM to judge the quality of agent output with strict JSON similarity.

    Inherits all functionality from BaseLLMOutputEvaluator but uses a different system prompt
    and output schema specific to strict JSON similarity evaluation.
    """

    system_prompt: str = (
        LLMJudgePromptTemplates.LLM_JUDGE_STRICT_JSON_SIMILARITY_SYSTEM_PROMPT
    )
    output_schema: type[BaseModel] = LLMJudgeStrictJSONSimilarityOutputSchema

    @classmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        return EvaluatorType.LLM_JUDGE_OUTPUT_STRICT_JSON_SIMILARITY.value
