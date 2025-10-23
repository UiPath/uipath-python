"""LLM-as-a-judge evaluator for subjective quality assessment of agent outputs."""

import json
from abc import abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, Field, model_validator

from .._helpers.evaluators_helpers import COMMUNITY_agents_SUFFIX
from ..models import (
    AgentExecution,
    EvaluationResult,
    LLMResponse,
    NumericEvaluationResult,
)
from ..models.llm_judge_types import (
    LLMJudgeOutputSchema,
    LLMJudgePromptTemplates,
)
from ..models.models import UiPathEvaluationError, UiPathEvaluationErrorCategory
from .base_evaluator import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
)

T = TypeVar("T", bound=BaseEvaluationCriteria)


class BaseLLMJudgeEvaluatorConfig(BaseEvaluatorConfig[T]):
    """Base config for all LLM evaluators.

    Generic over T (evaluation criteria type) to ensure type safety between
    the config's default_evaluation_criteria and the evaluator's expected criteria type.
    """

    prompt: str
    model: str = ""
    temperature: float = 0.0
    max_tokens: int | None = None


C = TypeVar("C", bound=BaseLLMJudgeEvaluatorConfig[Any])


class LLMJudgeMixin(BaseEvaluator[T, C, str]):
    """Mixin that provides common LLM judge functionality."""

    system_prompt: str = LLMJudgePromptTemplates.LLM_JUDGE_SYSTEM_PROMPT
    output_schema: type[BaseModel] = LLMJudgeOutputSchema
    actual_output_placeholder: str = "{{ActualOutput}}"
    expected_output_placeholder: str = "{{ExpectedOutput}}"
    llm_service: Callable[..., Any] | None = Field(
        default=None, exclude=True, description="The LLM service for evaluation"
    )

    @model_validator(mode="after")
    def validate_prompt_placeholders(self) -> "LLMJudgeMixin[T, C]":
        """Validate that prompt contains required placeholders."""
        if (
            self.actual_output_placeholder not in self.evaluator_config.prompt
            or self.expected_output_placeholder not in self.evaluator_config.prompt
        ):
            raise UiPathEvaluationError(
                code="INVALID_PROMPT_PLACEHOLDERS",
                title="Prompt must contain both {ActualOutput} and {ExpectedOutput} placeholders",
                detail="Prompt must contain both {ActualOutput} and {ExpectedOutput} placeholders",
                category=UiPathEvaluationErrorCategory.USER,
            )
        return self

    def model_post_init(self, __context: Any) -> None:
        """Initialize the LLM service if not provided."""
        super().model_post_init(__context)
        if self.llm_service is None:
            self.llm_service = self._get_llm_service()

    def _get_llm_service(self):
        """Get the LLM service from the UiPath instance."""
        from uipath import UiPath

        try:
            uipath = UiPath()
            return uipath.llm.chat_completions
        except Exception as e:
            raise UiPathEvaluationError(
                code="FAILED_TO_GET_LLM_SERVICE",
                title="Failed to get LLM service from the SDK and no otherLLM service provided",
                detail=f"Error: {e}",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            ) from e

    @abstractmethod
    def _get_actual_output(self, agent_execution: AgentExecution) -> Any:
        """Get the actual output from the agent execution. Must be implemented by concrete evaluator classes."""
        pass

    @abstractmethod
    def _get_expected_output(self, evaluation_criteria: T) -> Any:
        """Get the expected output from the evaluation criteria. Must be implemented by concrete evaluator classes."""
        pass

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: T,
    ) -> EvaluationResult:
        """Evaluate using an LLM as a judge."""
        evaluation_prompt = self._create_evaluation_prompt(
            agent_execution=agent_execution,
            evaluation_criteria=evaluation_criteria,
        )

        llm_response = await self._get_llm_response(evaluation_prompt)
        validated_justification = self.validate_justification(
            llm_response.justification
        )

        return NumericEvaluationResult(
            score=max(0.0, min(1.0, round(llm_response.score / 100.0, 2))),
            details=validated_justification,
        )

    def _create_evaluation_prompt(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: T,
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
        """Get response from the LLM."""
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
            "max_tokens": self.evaluator_config.max_tokens,
            "temperature": self.evaluator_config.temperature,
        }

        if self.llm_service is None:
            raise UiPathEvaluationError(
                code="LLM_SERVICE_NOT_INITIALIZED",
                title="LLM service not initialized",
                detail="LLM service not initialized",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            )

        try:
            response = await self.llm_service(**request_data)
        except Exception as e:
            raise UiPathEvaluationError(
                code="FAILED_TO_GET_LLM_RESPONSE",
                title="Failed to get LLM response",
                detail=f"Error: {e}",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            ) from e

        try:
            content = response.choices[-1].message.content
            if content is None:
                raise UiPathEvaluationError(
                    code="EMPTY_LLM_RESPONSE",
                    title="Empty LLM response",
                    detail="The LLM response message content was None.",
                    category=UiPathEvaluationErrorCategory.SYSTEM,
                )
            parsed_response = json.loads(str(content))
        except Exception as e:
            raise UiPathEvaluationError(
                code="FAILED_TO_PARSE_LLM_RESPONSE",
                title="Failed to parse LLM response",
                detail=f"Error: {e}",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            ) from e
        return LLMResponse(**parsed_response)
