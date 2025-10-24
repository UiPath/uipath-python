"""LLM-as-a-judge evaluator for subjective quality assessment of agent outputs."""

import json
from typing import Any, Optional

from pydantic import field_validator

from uipath.eval.models import NumericEvaluationResult

from ..._services import UiPathLlmChatService
from ..._utils.constants import COMMUNITY_agents_SUFFIX
from ..models.models import AgentExecution, EvaluationResult, LLMResponse
from .legacy_base_evaluator import (
    LegacyBaseEvaluator,
    LegacyEvaluationCriteria,
    LegacyEvaluatorConfig,
)


class LegacyLlmAsAJudgeEvaluatorConfig(LegacyEvaluatorConfig):
    """Configuration for legacy LLM-as-a-judge evaluators."""

    name: str = "LegacyLlmAsAJudgeEvaluator"


class LegacyLlmAsAJudgeEvaluator(LegacyBaseEvaluator[LegacyLlmAsAJudgeEvaluatorConfig]):
    """Legacy evaluator that uses an LLM to judge the quality of agent output."""

    prompt: str
    model: str
    actual_output_placeholder: str = "{{ActualOutput}}"
    expected_output_placeholder: str = "{{ExpectedOutput}}"
    llm: Optional[UiPathLlmChatService] = None

    @field_validator("prompt")
    @classmethod
    def validate_prompt_placeholders(cls, v: str) -> str:
        """Validate that prompt contains required placeholders."""
        if "{{ActualOutput}}" not in v or "{{ExpectedOutput}}" not in v:
            raise ValueError(
                "Prompt must contain both {ActualOutput} and {ExpectedOutput} placeholders"
            )
        return v

    def model_post_init(self, __context: Any):
        """Initialize the LLM service after model creation."""
        super().model_post_init(__context)
        self._initialize_llm()

    def _initialize_llm(self):
        """Initialize the LLM used for evaluation."""
        from uipath import UiPath

        uipath = UiPath()
        self.llm = uipath.llm

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: LegacyEvaluationCriteria,
    ) -> EvaluationResult:
        """Evaluate using an LLM as a judge.

        Sends the formatted prompt to the configured LLM and expects a JSON response
        with a numerical score (0-100) and justification.

            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - actual_output: The actual output from the agent
                - spans: The execution spans to use for the evaluation
            evaluation_criteria: The criteria to evaluate

        Returns:
            EvaluationResult: Numerical score with LLM justification as details
        """
        # Create the evaluation prompt
        evaluation_prompt = self._create_evaluation_prompt(
            expected_output=evaluation_criteria.expected_output,
            actual_output=agent_execution.agent_output,
        )

        llm_response = await self._get_llm_response(evaluation_prompt)

        return NumericEvaluationResult(
            score=llm_response.score,
            details=llm_response.justification,
        )

    def _create_evaluation_prompt(
        self, expected_output: Any, actual_output: Any
    ) -> str:
        """Create the evaluation prompt for the LLM."""
        formatted_prompt = self.prompt.replace(
            self.actual_output_placeholder,
            str(actual_output),
        )
        formatted_prompt = formatted_prompt.replace(
            self.expected_output_placeholder,
            str(expected_output),
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
        model = self.model
        if model.endswith(COMMUNITY_agents_SUFFIX):
            model = model.replace(COMMUNITY_agents_SUFFIX, "")

        # Prepare the request
        request_data = {
            "model": model,
            "messages": [{"role": "user", "content": evaluation_prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "evaluation_response",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 100,
                                "description": "Score between 0 and 100",
                            },
                            "justification": {
                                "type": "string",
                                "description": "Explanation for the score",
                            },
                        },
                        "required": ["score", "justification"],
                    },
                },
            },
        }

        response = await self.llm.chat_completions(**request_data)  # type: ignore
        return LLMResponse(**json.loads(response.choices[-1].message.content or "{}"))
