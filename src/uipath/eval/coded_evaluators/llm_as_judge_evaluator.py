"""LLM-as-a-judge evaluator for subjective quality assessment of agent outputs."""

import json
from typing import Any, TypeVar

from pydantic import BaseModel, model_validator

from ..._services import UiPathLlmChatService
from ..._utils.constants import COMMUNITY_agents_SUFFIX
from ..models import (
    AgentExecution,
    EvaluationResult,
    LLMResponse,
    NumericEvaluationResult,
)
from ..models.llm_judge_types import (
    LLMJudgeOutputSchema,
    LLMJudgePromptTemplates,
    LLMJudgeStrictJSONSimilarityOutputSchema,
)
from .output_evaluator import (
    OutputEvaluationCriteria,
    OutputEvaluator,
    OutputEvaluatorConfig,
)


class LLMJudgeEvaluatorConfig(OutputEvaluatorConfig):
    """Configuration for the llm as a judge evaluator."""

    name: str = "LLMJudgeEvaluator"
    prompt: str = LLMJudgePromptTemplates.LLM_JUDGE_DEFAULT_USER_PROMPT
    model: str


class LLMJudgeStrictJSONSimilarityEvaluatorConfig(LLMJudgeEvaluatorConfig):
    """Configuration for the llm as a judge strict json similarity evaluator."""

    name: str = "LLMJudgeStrictJSONSimilarityEvaluator"
    prompt: str = (
        LLMJudgePromptTemplates.LLM_JUDGE_STRICT_JSON_SIMILARITY_DEFAULT_USER_PROMPT
    )


C = TypeVar("C", bound=LLMJudgeEvaluatorConfig)


class BaseLLMJudgeEvaluator(OutputEvaluator[C]):
    """Evaluator that uses an LLM to judge the quality of agent output."""

    system_prompt: str = LLMJudgePromptTemplates.LLM_JUDGE_SYSTEM_PROMPT
    output_schema: type[BaseModel] = LLMJudgeOutputSchema
    actual_output_placeholder: str = "{{ActualOutput}}"
    expected_output_placeholder: str = "{{ExpectedOutput}}"
    llm_service: UiPathLlmChatService | None = None

    @model_validator(mode="after")
    def validate_prompt_placeholders(self) -> "BaseLLMJudgeEvaluator":
        """Validate that prompt contains required placeholders."""
        if (
            self.actual_output_placeholder not in self.evaluator_config.prompt
            or self.expected_output_placeholder not in self.evaluator_config.prompt
        ):
            raise ValueError(
                f"Prompt must contain both {self.actual_output_placeholder} and {self.expected_output_placeholder} placeholders"
            )
        return self

    def model_post_init(self, __context: Any):
        """Initialize the LLM service after model creation."""
        super().model_post_init(__context)
        self._initialize_llm_service()

    def _initialize_llm_service(self):
        """Initialize the LLM used for evaluation."""
        from uipath import UiPath

        uipath = UiPath()
        self.llm_service = uipath.llm

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: OutputEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate using an LLM as a judge.

        Sends the formatted prompt to the configured LLM and expects a JSON response
        with a numerical score (0-100) and justification.

            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - agent_output: The final output of the agent
                - agent_trace: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate

        Returns:
            EvaluationResult: Numerical score with LLM justification as details
        """
        # Create the evaluation prompt
        evaluation_prompt = self._create_evaluation_prompt(
            agent_execution=agent_execution,
            evaluation_criteria=evaluation_criteria,
        )

        llm_response = await self._get_llm_response(evaluation_prompt)

        return NumericEvaluationResult(
            score=round(llm_response.score / 100.0, 2),
            details=llm_response.justification,
        )

    def _create_evaluation_prompt(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: OutputEvaluationCriteria,
    ) -> str:
        """Create the evaluation prompt for the LLM."""
        formatted_prompt = self.evaluator_config.prompt.replace(
            self.actual_output_placeholder,
            str(self._get_actual_output(agent_execution)),
        )
        formatted_prompt = formatted_prompt.replace(
            self.expected_output_placeholder,
            str(self._get_expected_output(evaluation_criteria)),
        )

        return formatted_prompt

    async def _get_llm_response(self, evaluation_prompt: str) -> LLMResponse:
        """Get response from the LLM.

        Args:
            evaluation_prompt: The formatted prompt to send to the LLM

        Returns:
            LLMResponse with score and justification
        """
        # remove community-agents suffix from llm model name
        model = self.evaluator_config.model
        if model.endswith(COMMUNITY_agents_SUFFIX):
            model = model.replace(COMMUNITY_agents_SUFFIX, "")

        # Prepare the request
        request_data = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": evaluation_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "evaluation_response",
                    "schema": self.output_schema.model_json_schema(),
                },
            },
        }

        assert self.llm_service is not None, "LLM service not initialized"
        response = await self.llm_service.chat_completions(**request_data)
        return LLMResponse(**json.loads(str(response.choices[-1].message.content)))


class LLMJudgeEvaluator(BaseLLMJudgeEvaluator[LLMJudgeEvaluatorConfig]):
    """Evaluator that uses an LLM to judge the quality of agent output."""

    system_prompt: str = LLMJudgePromptTemplates.LLM_JUDGE_SYSTEM_PROMPT
    output_schema: type[BaseModel] = LLMJudgeOutputSchema


class LLMJudgeStrictJSONSimilarityEvaluator(
    BaseLLMJudgeEvaluator[LLMJudgeStrictJSONSimilarityEvaluatorConfig]
):
    """Evaluator that uses an LLM to judge the quality of agent output."""

    system_prompt: str = (
        LLMJudgePromptTemplates.LLM_JUDGE_STRICT_JSON_SIMILARITY_SYSTEM_PROMPT
    )
    output_schema: type[BaseModel] = LLMJudgeStrictJSONSimilarityOutputSchema
