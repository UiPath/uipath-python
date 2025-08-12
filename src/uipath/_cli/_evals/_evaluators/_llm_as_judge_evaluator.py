import json
from typing import Any, Dict

from ...._config import Config
from ...._execution_context import ExecutionContext
from ...._services.llm_gateway_service import UiPathLlmChatService
from ...._utils.constants import (
    ENV_BASE_URL,
    ENV_UIPATH_ACCESS_TOKEN,
    ENV_UNATTENDED_USER_ACCESS_TOKEN,
    COMMUNITY_agents_SUFFIX,
)
from .._models import EvaluationResult, LLMResponse
from .._models._evaluators import ScoreType
from ._evaluator_base import EvaluatorBase


class LlmAsAJudgeEvaluator(EvaluatorBase):
    """Evaluator that uses an LLM to judge the quality of outputs."""

    def __init__(self, prompt: str = "", model: str = "", target_output_key: str = "*"):
        """Initialize the LLM-as-a-judge evaluator.

        Args:
            prompt: The prompt template for the LLM
            model: The model to use for evaluation
            target_output_key: Key in output to evaluate ("*" for entire output)
        """
        super().__init__()
        self.actual_output_placeholder = "{{ActualOutput}}"
        self.expected_output_placeholder = "{{ExpectedOutput}}"
        self._initialize_llm()
        self.prompt = prompt
        self.model = model
        self.target_output_key: str = target_output_key

    def _initialize_llm(self):
        """Initialize the LLM used for evaluation."""
        import os

        base_url_value: str = os.getenv(ENV_BASE_URL)  # type: ignore
        secret_value: str = os.getenv(ENV_UNATTENDED_USER_ACCESS_TOKEN) or os.getenv(
            ENV_UIPATH_ACCESS_TOKEN
        )  # type: ignore
        config = Config(
            base_url=base_url_value,
            secret=secret_value,
        )
        self.llm = UiPathLlmChatService(config, ExecutionContext())

    async def evaluate(
        self,
        evaluation_id: str,
        evaluation_name: str,
        input_data: Dict[str, Any],
        expected_output: Dict[str, Any],
        actual_output: Dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate using an LLM as a judge.

        Args:
            evaluation_id: The ID of the evaluation being processed
            evaluation_name: The name of the evaluation
            input_data: The input data for the evaluation
            expected_output: The expected output
            actual_output: The actual output from the agent

        Returns:
            EvaluationResult containing the score and details
        """
        # Extract the target value to evaluate
        target_value = self._extract_target_value(actual_output)
        expected_value = self._extract_target_value(expected_output)

        # Create the evaluation prompt
        evaluation_prompt = self._create_evaluation_prompt(expected_value, target_value)

        llm_response = await self._get_llm_response(evaluation_prompt)

        return EvaluationResult(
            evaluation_id=evaluation_id,
            evaluation_name=evaluation_name,
            evaluator_id=self.id,
            evaluator_name=self.name,
            score=llm_response.score,
            input=input_data,
            expected_output=expected_output,
            actual_output=actual_output,
            details=llm_response.justification,
            score_type=ScoreType.NUMERICAL,
        )

    def _extract_target_value(self, output: Dict[str, Any]) -> Any:
        """Extract the target value from output based on target_output_key."""
        if self.target_output_key == "*":
            return output

        # Handle nested keys
        keys = self.target_output_key.split(".")
        value = output

        try:
            for key in keys:
                if isinstance(value, dict):
                    value = value[key]
                else:
                    return None
            return value
        except (KeyError, TypeError):
            return None

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
        try:
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

            response = await self.llm.chat_completions(**request_data)

            try:
                return LLMResponse(**json.loads(response.choices[-1].message.content))
            except (json.JSONDecodeError, ValueError) as e:
                return LLMResponse(
                    score=0.0, justification=f"Error parsing LLM response: {str(e)}"
                )

        except Exception as e:
            # Fallback in case of any errors
            return LLMResponse(
                score=0.0, justification=f"Error during LLM evaluation: {str(e)}"
            )
