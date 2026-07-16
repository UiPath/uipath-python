"""Helper functions for legacy LLM evaluators using function calling."""

import logging
import math
from typing import Any

from uipath.platform.chat.llm_gateway import (
    ToolDefinition,
    ToolFunctionDefinition,
    ToolParametersDefinition,
    ToolPropertyDefinition,
)

from ..models.models import LLMResponse

logger = logging.getLogger(__name__)


def create_evaluation_tool() -> ToolDefinition:
    """Create the standard evaluation tool definition for function calling.

    Returns:
        ToolDefinition with submit_evaluation function for structured output
    """
    return ToolDefinition(
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


def extract_tool_call_response(response: Any, model: str) -> LLMResponse:
    """Extract the evaluation response from the tool call.

    Args:
        response: The response from the LLM chat completions API
        model: The model name used for the request (for error logging)

    Returns:
        LLMResponse: Parsed response with score and justification

    Raises:
        ValueError: If the response format is invalid or missing required fields
    """
    try:
        if not response.choices or len(response.choices) == 0:
            error_msg = f"No choices in response from model {model}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        choice = response.choices[0]
        message = choice.message

        if not message.tool_calls or len(message.tool_calls) == 0:
            error_msg = f"No tool calls in response from model {model}"
            logger.error(f"❌ {error_msg}")
            logger.debug(f"Response: {response}")
            raise ValueError(error_msg)

        tool_call = message.tool_calls[0]
        arguments = tool_call.arguments

        if "score" not in arguments:
            error_msg = f"Missing 'score' in tool call arguments from model {model}"
            logger.error(f"❌ {error_msg}")
            logger.debug(f"Arguments: {arguments}")
            raise ValueError(error_msg)

        if "justification" not in arguments:
            error_msg = (
                f"Missing 'justification' in tool call arguments from model {model}"
            )
            logger.error(f"❌ {error_msg}")
            logger.debug(f"Arguments: {arguments}")
            raise ValueError(error_msg)

        score = float(arguments["score"])
        justification = str(arguments["justification"])

        if not math.isfinite(score):
            error_msg = (
                f"Non-finite score {score!r} in tool call arguments from model {model}"
            )
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        # Models occasionally emit corrupted numeric tool arguments despite the
        # 0-100 range stated in the tool schema (e.g. gemini-2.5-flash returning
        # 989898 or 950). An unclamped value poisons every run-level aggregate
        # downstream, so clamp here and surface the correction in the justification.
        if score < 0.0 or score > 100.0:
            clamped = max(0.0, min(100.0, score))
            logger.warning(
                f"⚠️ Model {model} returned out-of-range score {score}; clamping to {clamped}"
            )
            justification = (
                f"[Warning: model returned out-of-range score {score}; "
                f"clamped to {clamped}.]\n{justification}"
            )
            score = clamped

        logger.debug(
            f"✅ Extracted score: {score}, justification length: {len(justification)} chars"
        )

        return LLMResponse(score=score, justification=justification)

    except (KeyError, IndexError, AttributeError) as e:
        error_msg = f"Failed to extract tool call response from model {model}: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.debug(f"Response: {response}")
        raise ValueError(error_msg) from e
