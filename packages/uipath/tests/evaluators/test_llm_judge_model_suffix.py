"""Regression tests: LLM-judge evaluators must send the model name to the LLM
Gateway exactly as configured, including a "-community-agents" suffix.

Community/EU tenants' LLM Gateway routing rules are keyed on the suffixed
model id -- the same id AgentHub sends when it runs the agent itself.
Stripping the suffix before calling the Gateway causes a 417 "No llm routing
rule found for product agentsplaygroundfallback in EU using model ..." for
every Community/EU evaluation run, even though the identical model id works
fine for the agent.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from uipath.eval.evaluators import (
    LegacyContextPrecisionEvaluator,
    LegacyFaithfulnessEvaluator,
)
from uipath.eval.evaluators.base_legacy_evaluator import LegacyEvaluationCriteria
from uipath.eval.evaluators.legacy_llm_as_judge_evaluator import (
    LegacyLlmAsAJudgeEvaluator,
    LegacyLlmAsAJudgeEvaluatorConfig,
)
from uipath.eval.evaluators.legacy_trajectory_evaluator import (
    LegacyTrajectoryEvaluator,
    LegacyTrajectoryEvaluatorConfig,
)
from uipath.eval.evaluators.llm_judge_output_evaluator import LLMJudgeOutputEvaluator
from uipath.eval.evaluators.llm_judge_trajectory_evaluator import (
    LLMJudgeTrajectoryEvaluator,
)
from uipath.eval.models.models import LegacyEvaluatorCategory, LegacyEvaluatorType

COMMUNITY_MODEL = "gpt-5.4-2026-03-05-community-agents"


def _fake_tool_call_response(score: float = 90, justification: str = "ok"):
    tool_call = SimpleNamespace(
        arguments={"score": score, "justification": justification}
    )
    message = SimpleNamespace(tool_calls=[tool_call])
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


def _legacy_context_precision_evaluator() -> LegacyContextPrecisionEvaluator:
    return LegacyContextPrecisionEvaluator(
        id="context-precision",
        category=LegacyEvaluatorCategory.LlmAsAJudge,
        type=LegacyEvaluatorType.ContextPrecision,
        name="Context Precision",
        description="Evaluates context chunk relevance",
        createdAt="2025-01-01T00:00:00Z",
        updatedAt="2025-01-01T00:00:00Z",
        targetOutputKey="*",
        model=COMMUNITY_MODEL,
    )


class TestLegacyContextPrecisionEvaluatorSendsConfiguredModel:
    @pytest.mark.asyncio
    async def test_get_structured_llm_response_sends_full_model_name(self):
        evaluator = _legacy_context_precision_evaluator()
        mock_chat_completions = AsyncMock(return_value=_fake_tool_call_response())
        evaluator.llm = SimpleNamespace(chat_completions=mock_chat_completions)

        await evaluator._get_structured_llm_response("some evaluation prompt")

        sent_model = mock_chat_completions.call_args.kwargs["model"]
        assert sent_model == COMMUNITY_MODEL


def _legacy_faithfulness_evaluator() -> LegacyFaithfulnessEvaluator:
    return LegacyFaithfulnessEvaluator(
        id="faithfulness",
        category=LegacyEvaluatorCategory.LlmAsAJudge,
        type=LegacyEvaluatorType.Faithfulness,
        name="Faithfulness",
        description="Evaluates faithfulness of claims against context",
        createdAt="2025-01-01T00:00:00Z",
        updatedAt="2025-01-01T00:00:00Z",
        targetOutputKey="*",
        model=COMMUNITY_MODEL,
    )


class TestLegacyFaithfulnessEvaluatorSendsConfiguredModel:
    @pytest.mark.asyncio
    async def test_get_structured_llm_response_sends_full_model_name(self):
        evaluator = _legacy_faithfulness_evaluator()
        mock_chat_completions = AsyncMock(return_value=_fake_tool_call_response())
        evaluator.llm = SimpleNamespace(chat_completions=mock_chat_completions)

        await evaluator._get_structured_llm_response(
            "some evaluation prompt", "submit_result", {"type": "object"}
        )

        sent_model = mock_chat_completions.call_args.kwargs["model"]
        assert sent_model == COMMUNITY_MODEL


class TestLLMJudgeOutputEvaluatorSendsConfiguredModel:
    """Covers LLMJudgeMixin._get_llm_response -- the code path hit by
    'uipath-llm-judge-output-semantic-similarity' in production."""

    @pytest.mark.asyncio
    async def test_get_llm_response_sends_full_model_name_to_gateway(self):
        config = {
            "name": "TestEvaluator",
            "prompt": "Evaluate {{ActualOutput}} against {{ExpectedOutput}}",
            "model": COMMUNITY_MODEL,
        }
        with patch("uipath.platform.UiPath"):
            evaluator = LLMJudgeOutputEvaluator.model_validate(
                {"evaluatorConfig": config, "id": str(uuid.uuid4())}
            )
        mock_llm_service = AsyncMock(return_value=_fake_tool_call_response())
        evaluator.llm_service = mock_llm_service

        await evaluator._get_llm_response("some evaluation prompt")

        sent_model = mock_llm_service.call_args.kwargs["model"]
        assert sent_model == COMMUNITY_MODEL


class TestLLMJudgeTrajectoryEvaluatorSendsConfiguredModel:
    """Covers the same LLMJudgeMixin._get_llm_response via the trajectory
    evaluator -- this is the exact evaluator type from the reported
    production trace ('uipath-llm-judge-trajectory-similarity')."""

    @pytest.mark.asyncio
    async def test_get_llm_response_sends_full_model_name_to_gateway(self):
        config = {
            "name": "TestEvaluator",
            "prompt": "Judge {{AgentRunHistory}} against {{ExpectedAgentBehavior}}",
            "model": COMMUNITY_MODEL,
        }
        with patch("uipath.platform.UiPath"):
            evaluator = LLMJudgeTrajectoryEvaluator.model_validate(
                {"evaluatorConfig": config, "id": str(uuid.uuid4())}
            )
        mock_llm_service = AsyncMock(return_value=_fake_tool_call_response())
        evaluator.llm_service = mock_llm_service

        await evaluator._get_llm_response("some evaluation prompt")

        sent_model = mock_llm_service.call_args.kwargs["model"]
        assert sent_model == COMMUNITY_MODEL


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
        model=COMMUNITY_MODEL,
        createdAt="2026-05-14T00:00:00Z",
        updatedAt="2026-05-14T00:00:00Z",
    )


class TestLegacyTrajectoryEvaluatorSendsConfiguredModel:
    @pytest.mark.asyncio
    async def test_get_llm_response_sends_full_model_name_to_gateway(self):
        evaluator = _legacy_trajectory_evaluator()
        mock_chat_completions = AsyncMock(return_value=_fake_tool_call_response())
        evaluator.llm = SimpleNamespace(chat_completions=mock_chat_completions)

        await evaluator._get_llm_response("some evaluation prompt")

        sent_model = mock_chat_completions.call_args.kwargs["model"]
        assert sent_model == COMMUNITY_MODEL


def _legacy_llm_as_judge_evaluator() -> LegacyLlmAsAJudgeEvaluator:
    return LegacyLlmAsAJudgeEvaluator(
        id=str(uuid.uuid4()),
        name="Legacy LLM judge",
        config_type=LegacyLlmAsAJudgeEvaluatorConfig,
        evaluation_criteria_type=LegacyEvaluationCriteria,
        justification_type=str,
        category=LegacyEvaluatorCategory.LlmAsAJudge,
        type=LegacyEvaluatorType.Factuality,
        prompt="Compare {{ActualOutput}} to {{ExpectedOutput}}",
        model=COMMUNITY_MODEL,
        createdAt="2026-05-14T00:00:00Z",
        updatedAt="2026-05-14T00:00:00Z",
    )


class TestLegacyLlmAsAJudgeEvaluatorSendsConfiguredModel:
    @pytest.mark.asyncio
    async def test_get_llm_response_sends_full_model_name_to_gateway(self):
        evaluator = _legacy_llm_as_judge_evaluator()
        mock_chat_completions = AsyncMock(return_value=_fake_tool_call_response())
        evaluator.llm = SimpleNamespace(chat_completions=mock_chat_completions)

        await evaluator._get_llm_response("some evaluation prompt")

        sent_model = mock_chat_completions.call_args.kwargs["model"]
        assert sent_model == COMMUNITY_MODEL
