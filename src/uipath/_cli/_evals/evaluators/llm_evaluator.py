import json
from typing import Any, Dict, Optional

from .evaluator_base import EvaluatorBase
from ...._config import Config
from ...._execution_context import ExecutionContext
from ...._services.llm_gateway_service import UiPathLlmChatService
from ...._utils.constants import (
    COMMUNITY_AGENTS_SUFFIX,
    ENV_BASE_URL,
    ENV_UIPATH_ACCESS_TOKEN,
    ENV_UNATTENDED_USER_ACCESS_TOKEN,
)
from ..._utils._debug import console
from ..models import EvaluationResult, EvaluatorCategory, LLMResponse


class LLMEvaluator(EvaluatorBase):
    """Service for evaluating outputs using LLM."""

    def __init__(self, evaluator_config: Dict[str, Any]):
        """Initialize LLM evaluator.

        Args:
            evaluator_config: Configuration for the evaluator from evaluator JSON file
        """
        import os

        self.config = evaluator_config
        base_url_value = os.getenv(ENV_BASE_URL)
        secret_value = os.getenv(ENV_UNATTENDED_USER_ACCESS_TOKEN) or os.getenv(
            ENV_UIPATH_ACCESS_TOKEN
        )
        config = Config(
            base_url=base_url_value,  # type: ignore
            secret=secret_value,  # type: ignore
        )
        self.llm = UiPathLlmChatService(config, ExecutionContext())

        # Validate evaluator category
        if self.config.get("category") != EvaluatorCategory.LlmAsAJudge:
            raise ValueError("Evaluator must be of type LlmAsAJudge")

    async def evaluate(
        self,
        evaluation_id: str,
        evaluation_name: str,
        input_data: Dict[str, Any],
        expected_output: Dict[str, Any],
        actual_output: Dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate the actual output against expected output using LLM.

        Args:
            evaluation_id: ID of the evaluation
            evaluation_name: Name of the evaluation
            input_data: Input data used for the evaluation
            expected_output: Expected output from the evaluation
            actual_output: Actual output received

        Returns:
            EvaluationResult containing the evaluation score and details
        """
        # Prepare the prompt by replacing placeholders
        prompt = self.config["prompt"]
        prompt = prompt.replace(
            "{{ExpectedOutput}}", json.dumps(expected_output, indent=2)
        )
        content = prompt.replace(
            "{{ActualOutput}}", json.dumps(actual_output, indent=2)
        )

        model: Optional[str] = self.config.get("model", None)
        if not model:
            console.error("Evaluator model cannot be extracted")

        # remove community-agents suffix from llm model name
        if model.endswith(COMMUNITY_AGENTS_SUFFIX):
            model = model.replace(COMMUNITY_AGENTS_SUFFIX, "")

        response = await self.llm.chat_completions(
            messages=[{"role": "user", "content": content}],
            model=model,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "evaluation_result",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "score": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 100,
                                "description": "Similarity score between expected and actual output (0-100)",
                            },
                            "justification": {
                                "type": "string",
                                "description": "Detailed explanation of why this score was given",
                            },
                        },
                        "required": ["score", "justification"],
                        "additionalProperties": False,
                    },
                },
            },
        )
        try:
            llm_response = LLMResponse(
                **json.loads(response.choices[-1].message.content)
            )
        except Exception as e:
            raise Exception(f"Error parsing LLM response: {e}") from e
        # Leave those comments
        # llm_response = LLMResponse(similarity_score=90, score_justification="test justification")
        score = llm_response.score
        details = llm_response.justification

        if score < 0 or score > 100:
            raise ValueError(f"Score {score} is outside valid range 0-100")

        return EvaluationResult(
            evaluation_id=evaluation_id,
            evaluation_name=evaluation_name,
            evaluator_id=self.config["id"],
            evaluator_name=self.config["name"],
            score=score,
            input=input_data,
            expected_output=expected_output,
            actual_output=actual_output,
            details=details,
        )
