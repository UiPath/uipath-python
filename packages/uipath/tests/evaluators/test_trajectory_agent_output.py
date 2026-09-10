"""Regression tests for AE-2147.

The trajectory judges hand the run to the LLM through a single
``{{AgentRunHistory}}`` placeholder. That string was built from tool spans
alone, so the workload's own output never reached the judge and runs were
graded as if the agent had answered nothing.
"""

import uuid
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan

from uipath.eval.evaluators import LegacyTrajectoryEvaluator
from uipath.eval.evaluators.base_legacy_evaluator import LegacyEvaluationCriteria
from uipath.eval.evaluators.legacy_trajectory_evaluator import (
    LegacyTrajectoryEvaluatorConfig,
)
from uipath.eval.evaluators.llm_judge_trajectory_evaluator import (
    LLMJudgeTrajectoryEvaluator,
    TrajectoryEvaluationCriteria,
)
from uipath.eval.models.models import (
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
    WorkloadExecution,
)

AGENT_ANSWER = "Argentina won the most recent FIFA World Cup (Qatar 2022)."


def _web_search_span() -> ReadableSpan:
    """The one tool call from the AE-2147 repro run."""
    return ReadableSpan(
        name="Web_Search",
        start_time=1_756_233_000_000_000_000,
        end_time=1_756_233_007_000_000_000,
        attributes={
            "openinference.span.kind": "TOOL",
            "tool.name": "Web_Search",
            "input.value": "{}",
            "output.value": "{}",
        },
    )


def _workload_execution() -> WorkloadExecution:
    return WorkloadExecution(
        agent_input={"query": "Who won the most recent soccer World Cup?"},
        workload_output={"search_results_answer": AGENT_ANSWER},
        workload_trace=[_web_search_span()],
        expected_agent_behavior=(
            "The agent should perform a web search and return a clear answer "
            "identifying Argentina as the most recent winner."
        ),
    )


def test_llm_judge_trajectory_prompt_contains_the_agent_output() -> None:
    evaluator = LLMJudgeTrajectoryEvaluator.model_validate(
        {
            "id": str(uuid.uuid4()),
            "evaluatorConfig": {
                "name": "Default Trajectory Evaluator",
                "prompt": (
                    "ExpectedAgentBehavior:\n{{ExpectedAgentBehavior}}\n"
                    "AgentRunHistory:\n{{AgentRunHistory}}"
                ),
                "model": "gpt-4",
            },
        }
    )
    workload_execution = _workload_execution()

    prompt = evaluator._create_evaluation_prompt(
        workload_execution,
        TrajectoryEvaluationCriteria(
            expected_agent_behavior=workload_execution.expected_agent_behavior or ""
        ),
    )

    assert "Tool Call Response - Web_Search" in prompt
    assert AGENT_ANSWER in prompt


def test_legacy_trajectory_prompt_contains_the_agent_output() -> None:
    evaluator = LegacyTrajectoryEvaluator(
        id=str(uuid.uuid4()),
        name="Legacy trajectory",
        config_type=LegacyTrajectoryEvaluatorConfig,
        evaluation_criteria_type=LegacyEvaluationCriteria,
        justification_type=str,
        category=LegacyEvaluatorCategory.Trajectory,
        type=LegacyEvaluatorType.Trajectory,
        prompt="History:\n{{AgentRunHistory}}\nExpected:\n{{ExpectedAgentBehavior}}",
        createdAt="2026-05-14T00:00:00Z",
        updatedAt="2026-05-14T00:00:00Z",
    )
    workload_execution = _workload_execution()

    prompt = evaluator._create_evaluation_prompt(
        expected_agent_behavior=workload_execution.expected_agent_behavior,
        agent_run_history=workload_execution.workload_trace,
        workload_output=workload_execution.workload_output,
    )

    assert "Tool Call Response - Web_Search" in prompt
    assert AGENT_ANSWER in prompt


@pytest.mark.asyncio
async def test_legacy_trajectory_evaluate_sends_the_agent_output_to_the_llm(
    mocker: Any,
) -> None:
    """The output has to survive the real ``evaluate`` path, not just the helper."""
    evaluator = LegacyTrajectoryEvaluator(
        id=str(uuid.uuid4()),
        name="Legacy trajectory",
        config_type=LegacyTrajectoryEvaluatorConfig,
        evaluation_criteria_type=LegacyEvaluationCriteria,
        justification_type=str,
        category=LegacyEvaluatorCategory.Trajectory,
        type=LegacyEvaluatorType.Trajectory,
        prompt="History:\n{{AgentRunHistory}}\nExpected:\n{{ExpectedAgentBehavior}}",
        createdAt="2026-05-14T00:00:00Z",
        updatedAt="2026-05-14T00:00:00Z",
    )

    sent_prompts: list[str] = []
    tool_call = mocker.MagicMock()
    tool_call.arguments = {"score": 90, "justification": "answered correctly"}
    response = mocker.MagicMock()
    response.choices = [
        mocker.MagicMock(message=mocker.MagicMock(tool_calls=[tool_call]))
    ]

    async def chat_completions(**kwargs: Any) -> Any:
        sent_prompts.append(kwargs["messages"][0]["content"])
        return response

    evaluator.llm = mocker.MagicMock(chat_completions=chat_completions)

    result = await evaluator.evaluate(
        _workload_execution(),
        LegacyEvaluationCriteria.model_validate(
            {
                "expectedOutput": {},
                "expectedAgentBehavior": "The agent should identify Argentina.",
            }
        ),
    )

    assert result.score == 90
    assert AGENT_ANSWER in sent_prompts[0]
