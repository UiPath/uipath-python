"""LLM-as-a-judge evaluator for subjective quality assessment of agent outputs."""

import json
from typing import Any, Dict, Optional, TypeVar

from uipath.eval.models import EvaluationResult, LLMResponse, ScoreType
from uipath.tracing import UiPathEvalSpan

from ..._utils.constants import COMMUNITY_agents_SUFFIX
from .base_evaluator import BaseEvaluator

class LlmAsAJudgeEvaluator(BaseEvaluator[dict[str, Any]]):
    """Evaluator that uses an LLM to judge the quality of agent output."""

    def __init__(
        self,
        prompt: str,
        model: str,
        name: str = "LlmAsAJudgeEvaluator",
        description: Optional[str] = None,
        target_output_key: str = "*",
    ):
        """Initialize the LLM-as-a-judge evaluator.

        Args:
            prompt: The prompt template for the LLM with {{ActualOutput}} and {{ExpectedOutput}} placeholders
            model: The model to use for evaluation
            name: Display name for the evaluator
            description: Optional description of the evaluator's purpose
            target_output_key: Key in output to evaluate ("*" for entire output)

        Raises:
            ValueError: If prompt is missing required placeholders
        """
        super().__init__(name, description)
        self.actual_output_placeholder = "{{ActualOutput}}"
        self.expected_output_placeholder = "{{ExpectedOutput}}"
        self._validate_prompt(prompt)
        self._initialize_llm()
        self.prompt = prompt
        self.model = model
        self.target_output_key: str = target_output_key

    def _validate_prompt(self, prompt: str) -> None:
        missing_placeholders = []

        if self.actual_output_placeholder not in prompt:
            missing_placeholders.append(self.actual_output_placeholder)
        if self.expected_output_placeholder not in prompt:
            missing_placeholders.append(self.expected_output_placeholder)

        if missing_placeholders:
            raise ValueError(
                f"Prompt is missing required placeholders: {', '.join(missing_placeholders)}. "
                f"The prompt must contain both {self.actual_output_placeholder} and {self.expected_output_placeholder}."
            )

    def _initialize_llm(self):
        """Initialize the LLM used for evaluation."""
        from uipath import UiPath

        uipath = UiPath()
        self.llm = uipath.llm

    async def evaluate(
        self,
        agent_input: Optional[Dict[str, Any]],
        evaluation_criteria: dict[str, Any],
        actual_output: Dict[str, Any],
        uipath_eval_spans: Optional[list[UiPathEvalSpan]],
        execution_logs: str,
    ) -> EvaluationResult:
        """Evaluate using an LLM as a judge.

        Sends the formatted prompt to the configured LLM and expects a JSON response
        with a numerical score (0-100) and justification.

        Args:
            agent_input: The input provided to the agent (unused)
            evaluation_criteria: The evaluation criteria to evaluate
            actual_output: The actual output from the agent
            uipath_eval_spans: Execution spans from the agent (unused)
            execution_logs: Agent execution logs (unused)

        Returns:
            EvaluationResult: Numerical score with LLM justification as details
        """
        # Create the evaluation prompt
        evaluation_prompt = self._create_evaluation_prompt(
            evaluation_criteria, actual_output
        )

        llm_response = await self._get_llm_response(evaluation_prompt)
        return EvaluationResult(
            score=llm_response.score,
            details=llm_response.justification,
            score_type=ScoreType.NUMERICAL
            if llm_response.successful()
            else ScoreType.ERROR,
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
                    score=0.0,
                    justification=f"Error parsing LLM response: {str(e)}",
                    error=True,
                )

        except Exception as e:
            # Fallback in case of any errors
            return LLMResponse(
                score=0.0,
                justification=f"Error during LLM evaluation: {str(e)}",
                error=True,
            )
