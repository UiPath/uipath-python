"""LLM-as-a-judge evaluator for subjective quality assessment of agent outputs."""

import json
import logging
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
    BaseEvaluatorJustification,
)

T = TypeVar("T", bound=BaseEvaluationCriteria)

logger = logging.getLogger(__name__)


class LLMJudgeJustification(BaseEvaluatorJustification):
    """Justification for LLM judge evaluators."""

    justification: str


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


class LLMJudgeMixin(BaseEvaluator[T, C, LLMJudgeJustification]):
    """Mixin that provides common LLM judge functionality."""

    system_prompt: str = LLMJudgePromptTemplates.LLM_JUDGE_SYSTEM_PROMPT
    output_schema: type[BaseModel] = Field(default=LLMJudgeOutputSchema, exclude=True)
    actual_output_placeholder: str = "{{ActualOutput}}"
    expected_output_placeholder: str = "{{ExpectedOutput}}"
    llm_service: Callable[..., Any] | None = Field(
        default=None, exclude=True, description="The LLM service for evaluation"
    )

    @model_validator(mode="after")
    def validate_prompt_placeholders(self) -> "LLMJudgeMixin[T, C]":
        """Auto-add missing placeholders to prompt if not present.

        If both {{ActualOutput}} and {{ExpectedOutput}} are present, returns prompt as-is.
        If one is missing, appends the missing one at the end in a new section with tags.
        If both are missing, appends both at the end in separate sections with tags.

        Tags are added to help the LLM distinguish between outputs, especially for large JSONs.
        """
        has_actual = self.actual_output_placeholder in self.evaluator_config.prompt
        has_expected = self.expected_output_placeholder in self.evaluator_config.prompt

        # If both are present, return as-is
        if has_actual and has_expected:
            return self

        # Build the sections to add with opening and closing tags
        sections_to_add = []

        if not has_actual:
            sections_to_add.append(
                f"\n\n## Actual Output\n"
                f"<ActualOutput>\n"
                f"{self.actual_output_placeholder}\n"
                f"</ActualOutput>"
            )

        if not has_expected:
            sections_to_add.append(
                f"\n\n## Expected Output\n"
                f"<ExpectedOutput>\n"
                f"{self.expected_output_placeholder}\n"
                f"</ExpectedOutput>"
            )

        # Add missing sections to the end of the prompt
        self.evaluator_config.prompt += "".join(sections_to_add)

        return self

    def model_post_init(self, __context: Any) -> None:
        """Initialize the evaluator after model creation."""
        super().model_post_init(__context)

    def _get_llm_service(self):
        """Get the LLM service from the UiPath instance.

        Uses the normalized API which supports multiple model providers (OpenAI, Anthropic, Gemini, etc.).
        The normalized API endpoint checks against AllowedNormalizedModels configuration,
        which includes multi-vendor models that agents use.
        """
        from uipath.platform import UiPath

        try:
            uipath = UiPath(
                requesting_product="agentsplayground",
                requesting_feature="agents-evaluations",
                agenthub_config="agentsevals",
            )
            # Use llm (normalized API) for multi-vendor model support
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
            {
                "expected": str(self._get_expected_output(evaluation_criteria)),
                "actual": str(self._get_actual_output(agent_execution)),
                "justification": llm_response.justification,
            }
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
        expected_output = self._get_expected_output(evaluation_criteria)

        formatted_prompt = self.evaluator_config.prompt.replace(
            self.actual_output_placeholder,
            str(self._get_actual_output(agent_execution)),
        )
        formatted_prompt = formatted_prompt.replace(
            self.expected_output_placeholder,
            str(expected_output),
        )

        return formatted_prompt

    async def _get_llm_response(self, evaluation_prompt: str) -> LLMResponse:
        """Get response from the LLM using function calling for structured output.

        This method uses the Normalized API's function calling feature to ensure
        structured output across all model providers (OpenAI, Claude, Gemini).
        Function calling is more reliable than prompt-based JSON instructions
        and works consistently across all providers.
        """
        from uipath.platform.chat.llm_gateway import (
            RequiredToolChoice,
            ToolDefinition,
            ToolFunctionDefinition,
            ToolParametersDefinition,
            ToolPropertyDefinition,
        )

        # Remove community-agents suffix from llm model name
        model = self.evaluator_config.model
        if model.endswith(COMMUNITY_agents_SUFFIX):
            model = model.replace(COMMUNITY_agents_SUFFIX, "")

        # Define function/tool for structured output (works for ALL models via Normalized API)
        evaluation_tool = ToolDefinition(
            type="function",
            function=ToolFunctionDefinition(
                name="submit_evaluation",
                description="Submit the evaluation score and justification for the agent output",
                parameters=ToolParametersDefinition(
                    type="object",
                    properties={
                        "justification": ToolPropertyDefinition(
                            type="string",
                            description="Clear analysis of the evaluation explaining the reasoning behind the score",
                        ),
                        "score": ToolPropertyDefinition(
                            type="number",
                            description="Numeric score between 0 and 100 representing the evaluation result",
                        ),
                    },
                    required=["justification", "score"],
                ),
            ),
        )

        # Prepare the tool_choice object
        tool_choice = RequiredToolChoice()

        # Prepare the request with function calling
        request_data: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": evaluation_prompt},
            ],
            "temperature": self.evaluator_config.temperature,
            "tools": [evaluation_tool],
            "tool_choice": tool_choice,
        }

        # Set max_tokens - use explicit config value, or default for Claude 4.5 models
        max_tokens_value = self.evaluator_config.max_tokens
        if max_tokens_value is None:
            # Claude 4.5 models require max_tokens, set default to 8000
            if "claude-haiku-4-5" in model or "claude-sonnet-4-5" in model:
                max_tokens_value = 8000

        # Only include max_tokens if set (don't pass None to API)
        if max_tokens_value is not None:
            request_data["max_tokens"] = max_tokens_value

        # Lazy initialization - initialize LLM service only when needed
        # This ensures eval_set_run_id context is set before creating UiPath instance
        if self.llm_service is None:
            self.llm_service = self._get_llm_service()

        if self.llm_service is None:
            raise UiPathEvaluationError(
                code="LLM_SERVICE_NOT_INITIALIZED",
                title="LLM service not initialized",
                detail="LLM service not initialized",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            )

        # Log the request details (exclude non-JSON-serializable objects)
        logger.info(
            f"🤖 Calling LLM evaluator with model: {model} (using function calling)"
        )
        max_tokens_str = (
            str(max_tokens_value) if max_tokens_value is not None else "unset"
        )
        logger.debug(
            f"Request data: model={model}, max_tokens={max_tokens_str}, temperature={self.evaluator_config.temperature}, tool_choice=required"
        )

        # Log full request body for debugging
        import copy

        request_body_for_log = copy.deepcopy(request_data)
        # Convert tool_choice to dict for logging
        if "tool_choice" in request_body_for_log:
            request_body_for_log["tool_choice"] = request_body_for_log[
                "tool_choice"
            ].model_dump()
        # Convert tools to dict for logging
        if "tools" in request_body_for_log:
            request_body_for_log["tools"] = [
                t.model_dump() for t in request_body_for_log["tools"]
            ]
        logger.info(
            f"📤 Full request body:\n{json.dumps(request_body_for_log, indent=2)}"
        )

        try:
            response = await self.llm_service(**request_data)
        except Exception as e:
            # Enhanced error logging with details
            logger.error("=" * 80)
            logger.error("❌ LLM REQUEST FAILED")
            logger.error("=" * 80)
            logger.error(f"Model: {model}")
            logger.error("API Endpoint: Normalized API (/llm/api/chat/completions)")
            logger.error(f"Error Type: {type(e).__name__}")
            logger.error(f"Error Message: {str(e)}")

            # Try to extract HTTP error details if available
            if hasattr(e, "response"):
                logger.error(
                    f"HTTP Status Code: {e.response.status_code if hasattr(e.response, 'status_code') else 'N/A'}"
                )
                try:
                    error_body = (
                        e.response.json()
                        if hasattr(e.response, "json")
                        else str(e.response.content)
                    )
                    logger.error(
                        f"Response Body: {json.dumps(error_body, indent=2) if isinstance(error_body, dict) else error_body}"
                    )
                except Exception:
                    logger.error(
                        f"Response Body: {str(e.response.content) if hasattr(e.response, 'content') else 'N/A'}"
                    )

            max_tokens_str = (
                str(self.evaluator_config.max_tokens)
                if self.evaluator_config.max_tokens is not None
                else "unset"
            )
            logger.error(
                f"Request Details: model={model}, max_tokens={max_tokens_str}, temperature={self.evaluator_config.temperature}, tool_choice=required"
            )
            logger.error("=" * 80)

            raise UiPathEvaluationError(
                code="FAILED_TO_GET_LLM_RESPONSE",
                title="Failed to get LLM response",
                detail=f"Model: {model}, Error: {type(e).__name__}: {str(e)}",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            ) from e

        # Log successful response
        logger.info(f"✅ LLM response received successfully from {model}")
        logger.debug(f"Response: {response}")

        # Extract structured output from tool call
        return self._extract_tool_call_response(response, model)

    def _extract_tool_call_response(self, response: Any, model: str) -> LLMResponse:
        """Extract the evaluation response from the tool call.

        Args:
            response: The chat completion response containing tool calls
            model: The model name (for error logging)

        Returns:
            LLMResponse with score and justification

        Raises:
            UiPathEvaluationError: If tool call is missing or malformed
        """
        try:
            # Get the first choice
            if not response.choices or len(response.choices) == 0:
                raise UiPathEvaluationError(
                    code="INVALID_LLM_RESPONSE",
                    title="No choices in LLM response",
                    detail="The LLM response contained no choices",
                    category=UiPathEvaluationErrorCategory.SYSTEM,
                )

            choice = response.choices[0]
            message = choice.message

            # Check for tool calls
            if not message.tool_calls or len(message.tool_calls) == 0:
                # Log the actual response for debugging
                logger.error("=" * 80)
                logger.error("❌ NO TOOL CALL IN RESPONSE")
                logger.error("=" * 80)
                logger.error(f"Model: {model}")
                logger.error(f"Message content: {message.content}")
                logger.error("=" * 80)

                raise UiPathEvaluationError(
                    code="NO_TOOL_CALL",
                    title="LLM did not use the evaluation tool",
                    detail=f"Expected tool call but got text response: {message.content}",
                    category=UiPathEvaluationErrorCategory.SYSTEM,
                )

            # Extract the tool call arguments
            tool_call = message.tool_calls[0]
            arguments = tool_call.arguments

            logger.debug(f"Tool call arguments: {arguments}")

            # Validate required fields
            if "score" not in arguments:
                raise UiPathEvaluationError(
                    code="MISSING_SCORE",
                    title="Tool call missing required 'score' field",
                    detail=f"Tool arguments: {arguments}",
                    category=UiPathEvaluationErrorCategory.SYSTEM,
                )

            if "justification" not in arguments:
                raise UiPathEvaluationError(
                    code="MISSING_JUSTIFICATION",
                    title="Tool call missing required 'justification' field",
                    detail=f"Tool arguments: {arguments}",
                    category=UiPathEvaluationErrorCategory.SYSTEM,
                )

            # Parse and validate
            try:
                score = float(arguments["score"])
                justification = str(arguments["justification"])
            except (ValueError, TypeError) as e:
                raise UiPathEvaluationError(
                    code="INVALID_TOOL_ARGUMENTS",
                    title="Failed to parse tool call arguments",
                    detail=f"Error: {e}, Arguments: {arguments}",
                    category=UiPathEvaluationErrorCategory.SYSTEM,
                ) from e

            logger.info(f"📊 Parsed evaluation score: {score}")
            return LLMResponse(score=score, justification=justification)

        except UiPathEvaluationError:
            # Re-raise UiPathEvaluationErrors as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            logger.error("=" * 80)
            logger.error("❌ TOOL CALL EXTRACTION FAILED")
            logger.error("=" * 80)
            logger.error(f"Model: {model}")
            logger.error(f"Error: {type(e).__name__}: {str(e)}")
            logger.error(f"Response: {response}")
            logger.error("=" * 80)

            raise UiPathEvaluationError(
                code="FAILED_TO_EXTRACT_TOOL_CALL",
                title="Failed to extract evaluation from tool call",
                detail=f"Error: {type(e).__name__}: {str(e)}",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            ) from e
