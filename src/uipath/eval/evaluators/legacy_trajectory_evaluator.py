"""Trajectory evaluator for analyzing execution paths and decision sequences."""

import json
from typing import Any, Optional

from opentelemetry.sdk.trace import ReadableSpan
from pydantic import field_validator

from uipath.eval.models import EvaluationResult

from ..._services import UiPathLlmChatService
from ..._utils.constants import COMMUNITY_agents_SUFFIX
from ..models.models import (
    AgentExecution,
    LLMResponse,
    NumericEvaluationResult,
    TrajectoryEvaluationTrace,
)
from .legacy_base_evaluator import (
    LegacyBaseEvaluator,
    LegacyEvaluationCriteria,
    LegacyEvaluatorConfig,
)


class LegacyTrajectoryEvaluatorConfig(LegacyEvaluatorConfig):
    """Configuration for legacy trajectory evaluators."""

    name: str = "LegacyTrajectoryEvaluator"


class LegacyTrajectoryEvaluator(LegacyBaseEvaluator[LegacyTrajectoryEvaluatorConfig]):
    """Legacy evaluator that analyzes the trajectory/path taken to reach outputs."""

    prompt: str
    model: str
    expected_agent_behavior_placeholder: str = "{{ExpectedAgentBehavior}}"
    agent_run_history_placeholder: str = "{{AgentRunHistory}}"
    llm: Optional[UiPathLlmChatService] = None

    @field_validator("prompt")
    @classmethod
    def validate_prompt_placeholder(cls, v: str) -> str:
        """Validate that prompt contains required placeholders."""
        if "{{ExpectedAgentBehavior}}" not in v or "{{AgentRunHistory}}" not in v:
            raise ValueError(
                "Prompt must contain {ExpectedAgentBehavior} and {{AgentRunHistory}} placeholders"
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
        """Evaluate using trajectory analysis.

        Analyzes the execution path and decision sequence taken by the agent.

        Args:
            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - actual_output: The actual output from the agent
                - agent_trace: The execution spans to use for the evaluation
                - expected_agent_behavior: The expected agent behavior
            evaluation_criteria: The criteria to evaluate
        Returns:
            EvaluationResult: Score based on trajectory analysis

        Raises:
            NotImplementedError: This evaluator is not yet implemented
        """
        evaluation_prompt = self._create_evaluation_prompt(
            expected_agent_behavior=agent_execution.expected_agent_behavior,
            agent_run_history=agent_execution.agent_trace,
        )
        llm_response = await self._get_llm_response(evaluation_prompt)

        return NumericEvaluationResult(
            score=llm_response.score,
            details=llm_response.justification,
        )

    def _create_evaluation_prompt(
        self,
        expected_agent_behavior: Any,
        agent_run_history: Any,
    ) -> str:
        """Create the evaluation prompt for the LLM."""
        formatted_prompt = self.prompt.replace(
            self.expected_agent_behavior_placeholder,
            str(expected_agent_behavior),
        )

        # Trim extra properties from the spans (such as timestamps which are not relevant to the eval)
        if (
            isinstance(agent_run_history, list)
            and agent_run_history
            and isinstance(agent_run_history[0], ReadableSpan)
        ):
            trajectory_trace = TrajectoryEvaluationTrace.from_readable_spans(
                agent_run_history
            )
            agent_run_history = str(trajectory_trace.spans)
        else:
            agent_run_history = str(agent_run_history)

        formatted_prompt = formatted_prompt.replace(
            self.agent_run_history_placeholder,
            agent_run_history,
        )

        return formatted_prompt

    async def _get_llm_response(self, evaluation_prompt: str) -> LLMResponse:
        """Get response from the LLM.

        Args:
            evaluation_prompt: The formatted prompt to send to the LLM

        Returns:
            LLMResponse with score and justification
        """
        if not self.llm:
            raise ValueError("LLM service not initialized")

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
        return LLMResponse(**json.loads(response.choices[-1].message.content or "{}"))
