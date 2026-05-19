import uuid

from opentelemetry.sdk.trace import ReadableSpan

from uipath.eval.evaluators import LegacyTrajectoryEvaluator
from uipath.eval.evaluators.base_legacy_evaluator import LegacyEvaluationCriteria
from uipath.eval.evaluators.legacy_trajectory_evaluator import (
    LegacyTrajectoryEvaluatorConfig,
)
from uipath.eval.models.models import LegacyEvaluatorCategory, LegacyEvaluatorType


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


def test_legacy_trajectory_prompt_uses_compact_tool_history() -> None:
    long_prompt = "SYSTEM_PROMPT_" + ("x" * 10_000)
    spans = [
        ReadableSpan(
            name="agent_llm_call",
            start_time=0,
            end_time=1,
            attributes={
                "openinference.span.kind": "LLM",
                "input.value": f'{{"messages": [{{"role": "system", "content": "{long_prompt}"}}]}}',
                "output.value": '{"generations": []}',
            },
        ),
        ReadableSpan(
            name="search_profiles",
            start_time=1,
            end_time=2,
            attributes={
                "openinference.span.kind": "TOOL",
                "tool.name": "search_profiles",
                "input.value": '{"query": "mentor"}',
                "output.value": '{"content": "found mentor profile"}',
                "metadata": f'{{"agent_prompt": "{long_prompt}"}}',
            },
        ),
    ]

    prompt = _legacy_trajectory_evaluator()._create_evaluation_prompt(
        expected_agent_behavior="The agent should search matching profiles.",
        agent_run_history=spans,
    )

    assert "SYSTEM_PROMPT_" not in prompt
    assert "Tool: search_profiles" in prompt
    assert '{"query": "mentor"}' in prompt
    assert "found mentor profile" in prompt
    assert "agent_llm_call" not in prompt
