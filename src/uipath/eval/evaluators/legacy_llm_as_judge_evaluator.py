"""LLM-as-a-judge evaluator for subjective quality assessment of agent outputs."""

import logging
from typing import Any, Optional

from pydantic import field_validator

from uipath.eval.models import NumericEvaluationResult

from ..._utils.constants import COMMUNITY_agents_SUFFIX
from ...platform.chat import UiPathLlmChatService
from ...platform.chat.llm_gateway import RequiredToolChoice
from .._helpers.helpers import is_empty_value
from ..models.models import (
    AgentExecution,
    EvaluationResult,
    LLMResponse,
    UiPathEvaluationError,
    UiPathEvaluationErrorCategory,
)
from .base_legacy_evaluator import (
    BaseLegacyEvaluator,
    LegacyEvaluationCriteria,
    LegacyEvaluatorConfig,
)
from .legacy_llm_helpers import create_evaluation_tool, extract_tool_call_response

logger = logging.getLogger(__name__)


class LegacyLlmAsAJudgeEvaluatorConfig(LegacyEvaluatorConfig):
    """Configuration for legacy LLM-as-a-judge evaluators."""

    name: str = "LegacyLlmAsAJudgeEvaluator"


class LegacyLlmAsAJudgeEvaluator(BaseLegacyEvaluator[LegacyLlmAsAJudgeEvaluatorConfig]):
    """Legacy evaluator that uses an LLM to judge the quality of agent output."""

    prompt: str
    model: str
    actual_output_placeholder: str = "{{ActualOutput}}"
    expected_output_placeholder: str = "{{ExpectedOutput}}"
    llm: Optional[UiPathLlmChatService] = None

    @field_validator("prompt")
    @classmethod
    def validate_prompt_placeholders(cls, v: str) -> str:
        """Auto-add missing placeholders to prompt if not present.

        If both {{ActualOutput}} and {{ExpectedOutput}} are present, returns prompt as-is.
        If one is missing, appends the missing one at the end in a new section with tags.
        If both are missing, appends both at the end in separate sections with tags.

        Tags are added to help the LLM distinguish between outputs, especially for large JSONs.
        """
        has_actual = "{{ActualOutput}}" in v
        has_expected = "{{ExpectedOutput}}" in v

        # If both are present, return as-is
        if has_actual and has_expected:
            return v

        # Build the sections to add with opening and closing tags
        sections_to_add = []

        if not has_actual:
            sections_to_add.append(
                "\n\n## Actual Output\n"
                "<ActualOutput>\n"
                "{{ActualOutput}}\n"
                "</ActualOutput>"
            )

        if not has_expected:
            sections_to_add.append(
                "\n\n## Expected Output\n"
                "<ExpectedOutput>\n"
                "{{ExpectedOutput}}\n"
                "</ExpectedOutput>"
            )

        # Add missing sections to the end of the prompt
        return v + "".join(sections_to_add)

    def model_post_init(self, __context: Any):
        """Initialize the evaluator after model creation."""
        super().model_post_init(__context)

    def _initialize_llm(self):
        """Initialize the LLM used for evaluation."""
        from uipath.platform import UiPath

        uipath = UiPath(
            requesting_product="agentsplayground",
            requesting_feature="agents-evaluations",
            agenthub_config="agentsevals",
        )
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
        # Lazily initialize the LLM on first evaluation call
        if self.llm is None:
            self._initialize_llm()

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
        # Validate that expected output is not empty
        if is_empty_value(expected_output):
            logger.error(
                "❌ EMPTY_EXPECTED_OUTPUT: Expected output is empty or contains only empty values. "
                f"Received: {repr(expected_output)}"
            )
            raise UiPathEvaluationError(
                code="EMPTY_EXPECTED_OUTPUT",
                title="Expected output cannot be empty",
                detail="The evaluation criteria must contain a non-empty expected output.",
                category=UiPathEvaluationErrorCategory.USER,
            )

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
        """Get response from the LLM using universal function calling.

        Args:
            evaluation_prompt: The formatted prompt to send to the LLM

        Returns:
            LLMResponse with score and justification
        """
        # remove community-agents suffix from llm model name
        model = self.model
        if model.endswith(COMMUNITY_agents_SUFFIX):
            model = model.replace(COMMUNITY_agents_SUFFIX, "")

        # Create evaluation tool for function calling (works across all models)
        evaluation_tool = create_evaluation_tool()
        tool_choice = RequiredToolChoice()

        # Prepare the request with function calling
        request_data = {
            "model": model,
            "messages": [{"role": "user", "content": evaluation_prompt}],
            "tools": [evaluation_tool],
            "tool_choice": tool_choice,
        }

        assert self.llm, "LLM should be initialized before calling this method."
        response = await self.llm.chat_completions(**request_data)
        return extract_tool_call_response(response, model)
