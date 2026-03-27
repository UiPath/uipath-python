"""Internal utilities shared across evaluators."""

import copy
import json
import logging
from collections.abc import Callable
from typing import Any

from ..models.models import UiPathEvaluationError, UiPathEvaluationErrorCategory

logger = logging.getLogger(__name__)


async def _call_llm_with_logging(
    llm_service: Callable[..., Any],
    request_data: dict[str, Any],
    model: str,
) -> Any:
    """Call the LLM service with detailed request/response logging and error handling.

    Args:
        llm_service: The LLM chat completions callable
        request_data: The request payload to send
        model: The model name (for logging)

    Returns:
        The raw LLM response

    Raises:
        UiPathEvaluationError: If the LLM call fails
    """
    # Log the request details
    logger.info(
        f"🤖 Calling LLM evaluator with model: {model} (using function calling)"
    )
    logger.debug(f"Request data: model={model}, tool_choice=required")

    # Log full request body for debugging
    request_body_for_log = copy.deepcopy(request_data)
    if "tool_choice" in request_body_for_log:
        request_body_for_log["tool_choice"] = request_body_for_log[
            "tool_choice"
        ].model_dump()
    if "tools" in request_body_for_log:
        request_body_for_log["tools"] = [
            t.model_dump() for t in request_body_for_log["tools"]
        ]
    logger.info(f"📤 Full request body:\n{json.dumps(request_body_for_log, indent=2)}")

    try:
        response = await llm_service(**request_data)
    except Exception as e:
        logger.error("=" * 80)
        logger.error("❌ LLM REQUEST FAILED")
        logger.error("=" * 80)
        logger.error(f"Model: {model}")
        logger.error("API Endpoint: Normalized API (/llm/api/chat/completions)")
        logger.error(f"Error Type: {type(e).__name__}")
        logger.error(f"Error Message: {str(e)}")

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

        logger.error(f"Request Details: model={model}, tool_choice=required")
        logger.error("=" * 80)

        raise UiPathEvaluationError(
            code="FAILED_TO_GET_LLM_RESPONSE",
            title="Failed to get LLM response",
            detail=f"Model: {model}, Error: {type(e).__name__}: {str(e)}",
            category=UiPathEvaluationErrorCategory.SYSTEM,
        ) from e

    logger.info(f"✅ LLM response received successfully from {model}")
    logger.debug(f"Response: {response}")

    return response
