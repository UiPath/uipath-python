"""Reproduces the UV-16309 "no tool calls at all" corner case.

`trace_to_str` (eval/_helpers/evaluators_helpers.py) only ever renders spans
carrying a `tool.name` attribute. When an agent answers a request with plain
text and never calls a tool, there is nothing for it to render, so
`AgentRunHistory` comes back as an empty string - not because nothing
happened, but because `trace_to_str` only looks at tool-call spans. This is
deterministic (unlike the async export race covered by
test_execution_span_race.py), and it hid the agent's actual final answer
from both the legacy and LLM-judge trajectory evaluators, feeding the
"AgentRunHistory omits the agent's own text responses, causing false 0s
(empty) or unearned high scores (non-empty)" symptom.

Both evaluators now fall back to `WorkloadExecution.workload_output` (the
agent's real final answer, independent of the trace) whenever there were no
tool-call spans to render.
"""

import uuid

from uipath.eval.evaluators import LegacyTrajectoryEvaluator
from uipath.eval.evaluators.base_legacy_evaluator import LegacyEvaluationCriteria
from uipath.eval.evaluators.legacy_trajectory_evaluator import (
    LegacyTrajectoryEvaluatorConfig,
)
from uipath.eval.evaluators.llm_judge_trajectory_evaluator import (
    LLMJudgeTrajectoryEvaluator,
)
from uipath.eval.models.models import (
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
    WorkloadExecution,
)


def _legacy_trajectory_evaluator() -> LegacyTrajectoryEvaluator:
    return LegacyTrajectoryEvaluator(
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


def _llm_judge_trajectory_evaluator() -> LLMJudgeTrajectoryEvaluator:
    config = {
        "name": "LlmTrajectoryTest",
        "prompt": "History: {{AgentRunHistory}} Expected: {{ExpectedAgentBehavior}}",
        "model": "gpt-4",
    }
    return LLMJudgeTrajectoryEvaluator.model_validate(
        {"evaluatorConfig": config, "id": str(uuid.uuid4())}
    )


def test_legacy_trajectory_history_falls_back_to_final_output_with_no_tool_calls() -> (
    None
):
    """No tool-call spans at all -> AgentRunHistory must not be silently empty."""
    prompt_without_fallback = _legacy_trajectory_evaluator()._create_evaluation_prompt(
        expected_agent_behavior="The agent should answer the user's question.",
        agent_run_history=[],
    )
    # Without the fallback, a tool-free run leaves AgentRunHistory with nothing
    # but the empty span list's own repr - no sign the agent ever answered.
    assert "History:\n[]\nExpected:" in prompt_without_fallback

    prompt_with_fallback = _legacy_trajectory_evaluator()._create_evaluation_prompt(
        expected_agent_behavior="The agent should answer the user's question.",
        agent_run_history=[],
        workload_output="The mentor matching program starts on 2026-09-01.",
    )
    assert "Agent Final Response:" in prompt_with_fallback
    assert "The mentor matching program starts on 2026-09-01." in prompt_with_fallback


def test_llm_judge_trajectory_history_falls_back_to_final_output_with_no_tool_calls() -> (
    None
):
    """Same corner case, for the current (non-legacy) LLMJudgeTrajectoryEvaluator."""
    workload_execution = WorkloadExecution(
        agent_input={"question": "When does the mentor program start?"},
        workload_output="The mentor matching program starts on 2026-09-01.",
        workload_trace=[],
    )

    actual_output = _llm_judge_trajectory_evaluator()._get_actual_output(
        workload_execution
    )

    assert "Agent Final Response:" in actual_output
    assert "The mentor matching program starts on 2026-09-01." in actual_output
