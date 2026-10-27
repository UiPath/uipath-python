import uuid
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan

from uipath.eval._helpers.agent_output import (
    FINAL_RESPONSE_HEADER,
    append_agent_output,
    render_agent_output,
)
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
    LLMResponse,
    WorkloadExecution,
)

ANSWER = "I can only share your own mentorship records, not other people's."

# Shape a low-code conversational agent returns, copied from a cloud eval trace.
CONVERSATIONAL_OUTPUT = {
    "uipath__agent_response_messages": [
        {
            "role": "assistant",
            "contentParts": [
                {
                    "mimeType": "text/markdown",
                    "data": {"inline": ANSWER},
                    "citations": [],
                }
            ],
            "toolCalls": [],
        }
    ]
}


def _tool_span() -> ReadableSpan:
    return ReadableSpan(
        name="Tool call - GetUserContext",
        start_time=0,
        end_time=1,
        attributes={
            "tool.name": "GetUserContext",
            "input.value": '{"userSlackId": "U1"}',
            "output.value": '{"matches": []}',
        },
    )


def _legacy_evaluator(target_output_key: str = "*") -> LegacyTrajectoryEvaluator:
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
        targetOutputKey=target_output_key,
    )


def _llm_judge_evaluator() -> LLMJudgeTrajectoryEvaluator:
    return LLMJudgeTrajectoryEvaluator.model_validate(
        {
            "evaluatorConfig": {
                "name": "LlmTrajectoryTest",
                "prompt": "History: {{AgentRunHistory}} Expected: {{ExpectedAgentBehavior}}",
                "model": "gpt-4",
            },
            "id": str(uuid.uuid4()),
        }
    )


class TestRenderAgentOutput:
    def test_conversational_output_renders_message_text(self) -> None:
        rendered = render_agent_output(CONVERSATIONAL_OUTPUT)

        assert rendered == f"[assistant] {ANSWER}"

    def test_snake_case_output_renders_text_without_tool_calls(self) -> None:
        output = {
            "uipath__agent_response_messages": [
                {
                    "role": "assistant",
                    "content_parts": [
                        {"mime_type": "text/plain", "data": {"inline": ANSWER}}
                    ],
                    "tool_calls": [{"name": "Escalate", "input": {"reason": "x"}}],
                }
            ]
        }

        assert render_agent_output(output) == f"[assistant] {ANSWER}"

    def test_external_and_falsy_parts_are_kept(self) -> None:
        output = {
            "uipath__agent_response_messages": [
                {
                    "role": "assistant",
                    "contentParts": [
                        {
                            "mimeType": "text/plain",
                            "data": {"inline": "Report attached."},
                        },
                        {
                            "mimeType": "application/pdf",
                            "data": {"uri": "urn:uipath:cas:file:orchestrator:abc"},
                        },
                        {"mimeType": "application/json", "data": {"inline": False}},
                        {"mimeType": "application/json", "data": {"inline": 0}},
                        {"mimeType": "text/plain", "data": {"inline": ""}},
                    ],
                }
            ]
        }

        assert render_agent_output(output) == (
            "[assistant] Report attached.\n"
            "[assistant] Attachment (application/pdf): "
            "urn:uipath:cas:file:orchestrator:abc\n"
            "[assistant] false\n"
            "[assistant] 0"
        )

    def test_structured_fields_next_to_messages_are_kept(self) -> None:
        output = {**CONVERSATIONAL_OUTPUT, "category": "privacy"}

        rendered = render_agent_output(output)

        assert ANSWER in rendered
        assert '"category": "privacy"' in rendered
        assert "uipath__agent_response_messages" not in rendered

    def test_malformed_messages_fall_back_to_json(self) -> None:
        output = {"uipath__agent_response_messages": [{"unexpected": True}]}

        assert render_agent_output(output) == (
            '{\n  "uipath__agent_response_messages": [\n'
            '    {\n      "unexpected": true\n    }\n  ]\n}'
        )

    @pytest.mark.parametrize(
        ("output", "expected"),
        [
            ("plain answer", "plain answer"),
            ({"result": 42}, '{\n  "result": 42\n}'),
            ({}, "{}"),
        ],
    )
    def test_non_conversational_output(self, output: Any, expected: str) -> None:
        assert render_agent_output(output) == expected


class TestAppendAgentOutput:
    def test_empty_history_becomes_final_response_section(self) -> None:
        assert append_agent_output("", "answer") == f"{FINAL_RESPONSE_HEADER}\nanswer"

    def test_tool_history_is_kept_ahead_of_final_response(self) -> None:
        assert append_agent_output("tool history", "answer") == (
            f"tool history\n\n{FINAL_RESPONSE_HEADER}\nanswer"
        )

    def test_missing_output_leaves_history_untouched(self) -> None:
        assert append_agent_output("tool history", None) == "tool history"


class TestLLMJudgeTrajectoryHistory:
    def test_zero_tool_run_shows_agent_answer(self) -> None:
        execution = WorkloadExecution(
            agent_input={},
            workload_output=CONVERSATIONAL_OUTPUT,
            workload_trace=[],
        )

        history = _llm_judge_evaluator()._get_actual_output(execution)

        assert history == f"{FINAL_RESPONSE_HEADER}\n[assistant] {ANSWER}"

    def test_tool_run_shows_tool_calls_and_agent_answer(self) -> None:
        execution = WorkloadExecution(
            agent_input={},
            workload_output=CONVERSATIONAL_OUTPUT,
            workload_trace=[_tool_span()],
        )

        history = _llm_judge_evaluator()._get_actual_output(execution)

        assert "Tool: GetUserContext" in history
        assert history.endswith(f"{FINAL_RESPONSE_HEADER}\n[assistant] {ANSWER}")

    def test_attachment_output_is_downloaded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attachment_id = "0b9e4f3a-1c2d-4e5f-8a9b-0c1d2e3f4a5b"
        monkeypatch.setattr(
            "uipath.eval.evaluators.llm_judge_trajectory_evaluator.download_attachment_as_string",
            lambda key: ANSWER if key == attachment_id else "wrong id",
        )
        execution = WorkloadExecution(
            agent_input={},
            workload_output=f"urn:uipath:cas:file:orchestrator:{attachment_id}",
            workload_trace=[],
        )

        history = _llm_judge_evaluator()._get_actual_output(execution)

        assert history == f"{FINAL_RESPONSE_HEADER}\n{ANSWER}"


class TestLegacyTrajectoryHistory:
    def test_zero_tool_run_shows_agent_answer_instead_of_empty_list(self) -> None:
        prompt = _legacy_evaluator()._create_evaluation_prompt(
            expected_agent_behavior="Refuse to share other people's data.",
            agent_run_history=[],
            agent_output=CONVERSATIONAL_OUTPUT,
        )

        assert prompt.startswith(
            f"History:\n{FINAL_RESPONSE_HEADER}\n[assistant] {ANSWER}\nExpected:"
        )

    async def test_evaluate_resolves_target_output_key(self) -> None:
        evaluator = _legacy_evaluator(target_output_key="result")
        evaluator._initialize_llm = lambda: None  # type: ignore[method-assign]
        prompts: list[str] = []

        async def fake_llm_response(prompt: str) -> LLMResponse:
            prompts.append(prompt)
            return LLMResponse(score=100.0, justification="ok")

        evaluator._get_llm_response = fake_llm_response  # type: ignore[method-assign, assignment]
        execution = WorkloadExecution(
            agent_input={},
            workload_output={"result": ANSWER, "debug": "must not reach the judge"},
            workload_trace=[_tool_span()],
            expected_agent_behavior="Refuse to share other people's data.",
        )

        await evaluator.evaluate(
            execution,
            LegacyEvaluationCriteria(
                expected_output=None,
                expected_agent_behavior="Refuse to share other people's data.",
            ),
        )

        assert "Tool: GetUserContext" in prompts[0]
        assert f"{FINAL_RESPONSE_HEADER}\n{ANSWER}" in prompts[0]
        assert "must not reach the judge" not in prompts[0]
