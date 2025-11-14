"""Tests for evaluator evaluate() methods.

This module tests the actual evaluation functionality of all evaluators:
- ExactMatchEvaluator.evaluate()
- JsonSimilarityEvaluator.evaluate()
- LlmAsAJudgeEvaluator.evaluate()
- ToolCallOrderEvaluator.evaluate()
- ToolCallCountEvaluator.evaluate()
- LlmJudgeTrajectoryEvaluator.evaluate()
"""

import math
import uuid
from typing import Any

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from pytest_mock.plugin import MockerFixture

from uipath.eval.evaluators.contains_evaluator import (
    ContainsEvaluationCriteria,
    ContainsEvaluator,
)
from uipath.eval.evaluators.exact_match_evaluator import ExactMatchEvaluator
from uipath.eval.evaluators.json_similarity_evaluator import (
    JsonSimilarityEvaluator,
)
from uipath.eval.evaluators.llm_judge_output_evaluator import (
    LLMJudgeOutputEvaluator,
)
from uipath.eval.evaluators.llm_judge_trajectory_evaluator import (
    LLMJudgeTrajectoryEvaluator,
    TrajectoryEvaluationCriteria,
)
from uipath.eval.evaluators.output_evaluator import OutputEvaluationCriteria
from uipath.eval.evaluators.tool_call_args_evaluator import (
    ToolCallArgsEvaluationCriteria,
    ToolCallArgsEvaluator,
)
from uipath.eval.evaluators.tool_call_count_evaluator import (
    ToolCallCountEvaluationCriteria,
    ToolCallCountEvaluator,
)
from uipath.eval.evaluators.tool_call_order_evaluator import (
    ToolCallOrderEvaluationCriteria,
    ToolCallOrderEvaluator,
)
from uipath.eval.evaluators.tool_call_output_evaluator import (
    ToolCallOutputEvaluationCriteria,
    ToolCallOutputEvaluator,
    ToolCallOutputEvaluatorJustification,
)
from uipath.eval.models import NumericEvaluationResult
from uipath.eval.models.models import (
    AgentExecution,
    ToolCall,
    ToolOutput,
    UiPathEvaluationError,
)


@pytest.fixture
def sample_agent_execution() -> AgentExecution:
    """Create a sample AgentExecution for testing."""
    return AgentExecution(
        agent_input={"input": "Test input"},
        agent_output={"output": "Test output"},
        agent_trace=[],  # Empty trace for basic tests
    )


@pytest.fixture
def sample_agent_execution_with_trace() -> AgentExecution:
    """Create a sample AgentExecution with tool call trace."""
    # Mock spans that represent tool calls - simplified for testing
    mock_spans = [
        ReadableSpan(
            name="tool1",
            start_time=0,
            end_time=1,
            attributes={
                "tool.name": "tool1",
                "input.value": "{'arg1': 'value1'}",
                "output.value": '{"content": "output1"}',
            },
        ),
        ReadableSpan(
            name="tool2",
            start_time=1,
            end_time=2,
            attributes={
                "tool.name": "tool2",
                "input.value": "{'arg2': 'value2'}",
                "output.value": '{"content": "output2"}',
            },
        ),
        ReadableSpan(
            name="tool1",
            start_time=2,
            end_time=3,
            attributes={
                "tool.name": "tool1",
                "input.value": "{'arg1': 'value1'}",
                "output.value": '{"content": "output1"}',
            },
        ),
        ReadableSpan(
            name="tool2",
            start_time=3,
            end_time=4,
            attributes={
                "tool.name": "tool2",
                "input.value": "{'arg2': 'value2'}",
                "output.value": '{"content": "output2"}',
            },
        ),
    ]

    return AgentExecution(
        agent_input={"input": "Test input with tools"},
        agent_output={
            "output": "Test output with tools",
        },
        agent_trace=mock_spans,
    )


class TestExactMatchEvaluator:
    """Test ExactMatchEvaluator.evaluate() method."""

    @pytest.mark.asyncio
    async def test_exact_match_string_success(
        self, sample_agent_execution: AgentExecution
    ) -> None:
        """Test exact match with matching strings."""
        config = {
            "name": "ExactMatchTest",
            "case_sensitive": True,
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(expected_output={"output": "Test output"})  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_exact_match_string_failure(
        self, sample_agent_execution: AgentExecution
    ) -> None:
        """Test exact match with non-matching strings."""
        config = {
            "name": "ExactMatchTest",
            "case_sensitive": True,
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(
            expected_output={"output": "Different output"}  # pyright: ignore[reportCallIssue]
        )

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_exact_match_negated(
        self, sample_agent_execution: AgentExecution
    ) -> None:
        """Test exact match with negated criteria."""
        config = {
            "name": "ExactMatchTest",
            "case_sensitive": True,
            "negated": True,
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(
            expected_output={"output": "Test output"},  # pyright: ignore[reportCallIssue]
        )

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_exact_match_validate_and_evaluate_criteria(
        self, sample_agent_execution: AgentExecution
    ) -> None:
        """Test exact match using validate_and_evaluate_criteria."""
        config = {
            "name": "ExactMatchTest",
            "case_sensitive": True,
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        raw_criteria = {"expected_output": {"output": "Test output"}}

        result = await evaluator.validate_and_evaluate_criteria(
            sample_agent_execution, raw_criteria
        )

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0


class TestContainsEvaluator:
    """Test ContainsEvaluator.evaluate() method."""

    @pytest.mark.asyncio
    async def test_contains_evaluator(
        self, sample_agent_execution: AgentExecution
    ) -> None:
        """Test contains evaluator."""
        config = {
            "name": "ContainsTest",
            "target_output_key": "output",
            "default_evaluation_criteria": {"search_text": "Test output"},
        }
        evaluator = ContainsEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ContainsEvaluationCriteria(search_text="Test output")
        result = await evaluator.evaluate(sample_agent_execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_contains_evaluator_negated(
        self, sample_agent_execution: AgentExecution
    ) -> None:
        """Test contains evaluator with negated criteria."""
        config = {
            "name": "ContainsTest",
            "negated": True,
            "target_output_key": "output",
            "default_evaluation_criteria": {"search_text": "Test output"},
        }
        evaluator = ContainsEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ContainsEvaluationCriteria(search_text="Test output")
        result = await evaluator.evaluate(sample_agent_execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_contains_evaluator_validate_and_evaluate_criteria(
        self, sample_agent_execution: AgentExecution
    ) -> None:
        """Test contains evaluator with validate_and_evaluate_criteria."""
        config = {
            "name": "ContainsTest",
            "target_output_key": "*",
            "default_evaluation_criteria": {"search_text": "Test output"},
        }
        evaluator = ContainsEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ContainsEvaluationCriteria(search_text="Test output")
        result = await evaluator.validate_and_evaluate_criteria(
            sample_agent_execution, criteria
        )
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0


class TestJsonSimilarityEvaluator:
    """Test JsonSimilarityEvaluator.evaluate() method."""

    @pytest.mark.asyncio
    async def test_json_similarity_identical(self) -> None:
        """Test JSON similarity with identical structures."""
        execution = AgentExecution(
            agent_input={"input": "Test"},
            agent_output={"name": "John", "age": 30, "city": "NYC"},
            agent_trace=[],
        )
        config = {
            "name": "JsonSimilarityTest",
        }
        evaluator = JsonSimilarityEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(
            expected_output={"name": "John", "age": 30, "city": "NYC"}  # pyright: ignore[reportCallIssue]
        )

        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_json_similarity_partial_match(self) -> None:
        """Test JSON similarity with partial matches."""
        execution = AgentExecution(
            agent_input={"input": "Test"},
            agent_output={"name": "John", "age": 30, "city": "LA"},
            agent_trace=[],
        )
        config = {
            "name": "JsonSimilarityTest",
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        evaluator = JsonSimilarityEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(
            expected_output={"name": "John", "age": 30, "city": "NYC"}  # pyright: ignore[reportCallIssue]
        )

        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert math.isclose(result.score, 0.666, abs_tol=1e-3)

    @pytest.mark.asyncio
    async def test_json_similarity_validate_and_evaluate_criteria(self) -> None:
        """Test JSON similarity using validate_and_evaluate_criteria."""
        execution = AgentExecution(
            agent_input={"input": "Test"},
            agent_output={"name": "John", "age": 30, "city": "NYC"},
            agent_trace=[],
        )
        config = {
            "name": "JsonSimilarityTest",
        }
        evaluator = JsonSimilarityEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        raw_criteria = {"expected_output": {"name": "John", "age": 30, "city": "NYC"}}

        result = await evaluator.validate_and_evaluate_criteria(execution, raw_criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0


class TestToolCallOrderEvaluator:
    """Test ToolCallOrderEvaluator.evaluate() method."""

    @pytest.mark.asyncio
    async def test_tool_call_order_perfect_match(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call order with perfect order match."""

        config = {
            "name": "ToolOrderTest",
            "strict": True,
        }

        evaluator = ToolCallOrderEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallOrderEvaluationCriteria(
            tool_calls_order=["tool1", "tool2", "tool1", "tool2"]
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_tool_call_order_no_perfect_match(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call order with perfect order match."""

        config = {
            "name": "ToolOrderTest",
            "strict": True,
        }

        evaluator = ToolCallOrderEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallOrderEvaluationCriteria(
            tool_calls_order=["tool1", "tool1", "tool2", "tool2"]
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_tool_call_order_lcs_match(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call order with lcs order match."""

        config = {
            "name": "ToolOrderTest",
            "strict": False,
        }
        evaluator = ToolCallOrderEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallOrderEvaluationCriteria(
            tool_calls_order=["tool1", "tool1", "tool2", "tool2"]
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.75

    @pytest.mark.asyncio
    async def test_tool_call_order_validate_and_evaluate_criteria(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call order using validate_and_evaluate_criteria."""
        config = {
            "name": "ToolOrderTest",
            "strict": True,
        }
        evaluator = ToolCallOrderEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        raw_criteria = {"tool_calls_order": ["tool1", "tool2", "tool1", "tool2"]}

        result = await evaluator.validate_and_evaluate_criteria(
            sample_agent_execution_with_trace, raw_criteria
        )

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0


class TestToolCallCountEvaluator:
    """Test ToolCallCountEvaluator.evaluate() method."""

    @pytest.mark.asyncio
    async def test_tool_call_count_exact_match(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call count with exact count match."""
        config = {
            "name": "ToolCountTest",
            "strict": True,
        }
        evaluator = ToolCallCountEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallCountEvaluationCriteria(
            tool_calls_count={"tool1": ("=", 2), "tool2": ("=", 2)}
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_tool_call_count_with_gt(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call count with strict count match."""
        config = {
            "name": "ToolCountTest",
            "strict": True,
        }
        evaluator = ToolCallCountEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallCountEvaluationCriteria(
            tool_calls_count={"tool1": (">", 1), "tool2": (">", 1)}
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_tool_call_count_no_exact_match(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call count with no exact count match."""
        config = {
            "name": "ToolCountTest",
            "strict": True,
        }
        evaluator = ToolCallCountEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallCountEvaluationCriteria(
            tool_calls_count={"tool1": ("=", 2), "tool2": ("=", 1)}
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_tool_call_count_partial_match(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call count with partial count match."""
        config = {
            "name": "ToolCountTest",
            "strict": False,
        }
        evaluator = ToolCallCountEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallCountEvaluationCriteria(
            tool_calls_count={"tool1": ("=", 2), "tool2": ("=", 1)}
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.5

    @pytest.mark.asyncio
    async def test_tool_call_count_validate_and_evaluate_criteria(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call count using validate_and_evaluate_criteria."""
        config = {
            "name": "ToolCountTest",
            "strict": True,
        }
        evaluator = ToolCallCountEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        raw_criteria = {"tool_calls_count": {"tool1": ("=", 2), "tool2": ("=", 2)}}

        result = await evaluator.validate_and_evaluate_criteria(
            sample_agent_execution_with_trace, raw_criteria
        )

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0


class TestToolCallArgsEvaluator:
    """Test ToolCallArgsEvaluator.evaluate() method."""

    @pytest.mark.asyncio
    async def test_tool_call_args_perfect_match(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call args with perfect match."""
        config = {
            "name": "ToolArgsTest",
            "strict": True,
        }
        evaluator = ToolCallArgsEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallArgsEvaluationCriteria(
            tool_calls=[
                ToolCall(name="tool1", args={"arg1": "value1"}),
                ToolCall(name="tool2", args={"arg2": "value2"}),
                ToolCall(name="tool1", args={"arg1": "value1"}),
                ToolCall(name="tool2", args={"arg2": "value2"}),
            ]
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_tool_call_args_partial_match(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call args with partial match."""
        config = {
            "name": "ToolArgsTest",
            "strict": False,
        }
        evaluator = ToolCallArgsEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallArgsEvaluationCriteria(
            tool_calls=[
                ToolCall(name="tool1", args={"arg1": "value1"}),
                ToolCall(name="tool2", args={"arg2": "value1"}),
                ToolCall(name="tool1", args={"arg1": "value1"}),
                ToolCall(name="tool2", args={"arg2": "value2"}),
            ]
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.75

    @pytest.mark.asyncio
    async def test_tool_call_args_validate_and_evaluate_criteria(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call args using validate_and_evaluate_criteria."""
        config = {
            "name": "ToolArgsTest",
            "strict": True,
        }
        evaluator = ToolCallArgsEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        raw_criteria = {
            "tool_calls": [
                {"name": "tool1", "args": {"arg1": "value1"}},
                {"name": "tool2", "args": {"arg2": "value2"}},
                {"name": "tool1", "args": {"arg1": "value1"}},
                {"name": "tool2", "args": {"arg2": "value2"}},
            ]
        }

        result = await evaluator.validate_and_evaluate_criteria(
            sample_agent_execution_with_trace, raw_criteria
        )

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0


class TestToolCallOutputEvaluator:
    """Test ToolCallOutputEvaluator.evaluate() method."""

    @pytest.mark.asyncio
    async def test_tool_call_output_perfect_match(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call output with perfect output match."""
        config = {
            "name": "ToolOutputTest",
            "strict": True,
        }
        evaluator = ToolCallOutputEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallOutputEvaluationCriteria(
            tool_outputs=[
                ToolOutput(name="tool1", output="output1"),
                ToolOutput(name="tool2", output="output2"),
                ToolOutput(name="tool1", output="output1"),
                ToolOutput(name="tool2", output="output2"),
            ]
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_tool_call_output_partial_match(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call output with partial output match."""
        config = {
            "name": "ToolOutputTest",
            "strict": False,
        }
        evaluator = ToolCallOutputEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallOutputEvaluationCriteria(
            tool_outputs=[
                ToolOutput(name="tool1", output="output1"),
                ToolOutput(name="tool2", output="wrong_output"),
                ToolOutput(name="tool1", output="output1"),
                ToolOutput(name="tool2", output="output2"),
            ]
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.75

    @pytest.mark.asyncio
    async def test_tool_call_output_no_match_strict(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call output with no match in strict mode."""
        config = {
            "name": "ToolOutputTest",
            "strict": True,
        }
        evaluator = ToolCallOutputEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallOutputEvaluationCriteria(
            tool_outputs=[
                ToolOutput(name="tool1", output="wrong_output1"),
                ToolOutput(name="tool2", output="output2"),
                ToolOutput(name="tool1", output="output1"),
                ToolOutput(name="tool2", output="output2"),
            ]
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_tool_call_output_partial_match_non_strict(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call output with partial match in non-strict mode."""
        config = {
            "name": "ToolOutputTest",
            "strict": False,
        }
        evaluator = ToolCallOutputEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallOutputEvaluationCriteria(
            tool_outputs=[
                ToolOutput(name="tool1", output="wrong_output1"),
                ToolOutput(name="tool2", output="output2"),
            ]
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.5

    @pytest.mark.asyncio
    async def test_tool_call_output_empty_criteria(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call output with empty criteria."""
        config = {
            "name": "ToolOutputTest",
            "strict": False,
        }
        evaluator = ToolCallOutputEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallOutputEvaluationCriteria(tool_outputs=[])

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_tool_call_output_validate_and_evaluate_criteria(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test tool call output using validate_and_evaluate_criteria."""
        config = {
            "name": "ToolOutputTest",
            "strict": True,
        }
        evaluator = ToolCallOutputEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        raw_criteria = {
            "tool_outputs": [
                {"name": "tool1", "output": "output1"},
                {"name": "tool2", "output": "output2"},
                {"name": "tool1", "output": "output1"},
                {"name": "tool2", "output": "output2"},
            ]
        }

        result = await evaluator.validate_and_evaluate_criteria(
            sample_agent_execution_with_trace, raw_criteria
        )

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0


class TestLlmAsAJudgeEvaluator:
    """Test LlmAsAJudgeEvaluator.evaluate() method."""

    @pytest.mark.asyncio
    async def test_llm_judge_basic_evaluation(
        self, sample_agent_execution: AgentExecution, mocker: MockerFixture
    ) -> None:
        """Test LLM as judge basic evaluation functionality."""
        # Mock the UiPath constructor to avoid authentication
        mock_uipath = mocker.MagicMock()
        mock_llm = mocker.MagicMock()
        mock_uipath.llm = mock_llm

        # Mock the chat completions response as an async method
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 80, "justification": "Good response that meets criteria"}'
                )
            )
        ]

        # Make chat_completions an async method
        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        mock_llm.chat_completions = mock_chat_completions

        mocker.patch("uipath.UiPath", return_value=mock_uipath)

        config = {
            "name": "LlmJudgeTest",
            "prompt": "Rate this output: {{ActualOutput}} vs {{ExpectedOutput}}",
            "model": "gpt-4o-2024-08-06",
        }
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )

        criteria = OutputEvaluationCriteria(expected_output="Expected output")  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        # Verify the result
        assert hasattr(result, "score")
        assert isinstance(result, NumericEvaluationResult), f"Result is {result}"
        assert result.score == 0.8, f"Result score is {result.score}"

    @pytest.mark.asyncio
    async def test_llm_judge_basic_evaluation_with_llm_service(
        self, sample_agent_execution: AgentExecution, mocker: MockerFixture
    ) -> None:
        """Test LLM judge basic evaluation functionality with a custom LLM service."""
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 80, "justification": "Good response that meets criteria"}'
                )
            )
        ]

        # Make chat_completions an async method
        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        config = {
            "name": "LlmJudgeTest",
            "prompt": "Rate this output: {{ActualOutput}} vs {{ExpectedOutput}}",
            "model": "gpt-4o-2024-08-06",
        }
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {
                "config": config,
                "llm_service": mock_chat_completions,
                "id": str(uuid.uuid4()),
            }
        )

        criteria = OutputEvaluationCriteria(expected_output="Expected output")  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        # Verify the result
        assert hasattr(result, "score")
        assert isinstance(result, NumericEvaluationResult), f"Result is {result}"
        assert result.score == 0.8, f"Result score is {result.score}"

    @pytest.mark.asyncio
    async def test_llm_judge_validate_and_evaluate_criteria(
        self, sample_agent_execution: AgentExecution, mocker: MockerFixture
    ) -> None:
        """Test LLM judge using validate_and_evaluate_criteria."""
        # Mock the UiPath constructor to avoid authentication
        mock_uipath = mocker.MagicMock()
        mock_llm = mocker.MagicMock()
        mock_uipath.llm = mock_llm

        # Mock the chat completions response as an async method
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 75, "justification": "Good response using raw criteria"}'
                )
            )
        ]

        # Make chat_completions an async method
        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        mock_llm.chat_completions = mock_chat_completions

        # Mock the UiPath import and constructor
        mocker.patch("uipath.UiPath", return_value=mock_uipath)

        config = {
            "name": "LlmJudgeTest",
            "prompt": "Rate this output: {{ActualOutput}} vs {{ExpectedOutput}}",
            "model": "gpt-4",
        }
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        raw_criteria = {"expected_output": "Expected output"}

        result = await evaluator.validate_and_evaluate_criteria(
            sample_agent_execution, raw_criteria
        )

        # Verify the result
        assert hasattr(result, "score")
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.75


class TestLlmJudgeTrajectoryEvaluator:
    """Test LlmJudgeTrajectoryEvaluator.evaluate() method."""

    @pytest.mark.asyncio
    async def test_llm_trajectory_basic_evaluation(
        self, sample_agent_execution: AgentExecution, mocker: MockerFixture
    ) -> None:
        """Test LLM trajectory judge basic evaluation functionality."""
        # Mock the UiPath constructor to avoid authentication
        mock_uipath = mocker.MagicMock()
        mock_llm = mocker.MagicMock()
        mock_uipath.llm = mock_llm

        # Mock the chat completions response as an async method
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 90, "justification": "The agent followed the expected behavior and met the criteria"}'
                )
            )
        ]

        # Make chat_completions an async method
        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        mock_llm.chat_completions = mock_chat_completions

        # Mock the UiPath import and constructor
        mocker.patch("uipath.UiPath", return_value=mock_uipath)

        config = {
            "name": "LlmTrajectoryTest",
            "prompt": "Evaluate this trajectory: {{AgentRunHistory}} vs {{ExpectedAgentBehavior}} given the following input: {{UserOrSyntheticInput}} instructions: {{SimulationInstructions}}",
            "model": "gpt-4",
        }
        evaluator = LLMJudgeTrajectoryEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )

        criteria = TrajectoryEvaluationCriteria(
            expected_agent_behavior="Agent should respond helpfully"
        )

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        # Verify the result
        assert hasattr(result, "score")
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.9

    @pytest.mark.asyncio
    async def test_llm_trajectory_validate_and_evaluate_criteria(
        self, sample_agent_execution: AgentExecution, mocker: MockerFixture
    ) -> None:
        """Test LLM trajectory judge using validate_and_evaluate_criteria."""
        # Mock the UiPath constructor to avoid authentication
        mock_uipath = mocker.MagicMock()
        mock_llm = mocker.MagicMock()
        mock_uipath.llm = mock_llm

        # Mock the chat completions response as an async method
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 85, "justification": "The agent behavior was good using raw criteria"}'
                )
            )
        ]

        # Make chat_completions an async method
        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        mock_llm.chat_completions = mock_chat_completions

        # Mock the UiPath import and constructor
        mocker.patch("uipath.UiPath", return_value=mock_uipath)

        config = {
            "name": "LlmTrajectoryTest",
            "prompt": "Evaluate this trajectory: {{AgentRunHistory}} vs {{ExpectedAgentBehavior}} given the following input: {{UserOrSyntheticInput}} instructions: {{SimulationInstructions}}",
            "model": "gpt-4",
        }
        evaluator = LLMJudgeTrajectoryEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        raw_criteria = {"expected_agent_behavior": "Agent should respond helpfully"}

        result = await evaluator.validate_and_evaluate_criteria(
            sample_agent_execution, raw_criteria
        )

        # Verify the result
        assert hasattr(result, "score")
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.85


class TestEvaluatorErrorHandling:
    """Test error handling in evaluators."""

    @pytest.mark.asyncio
    async def test_invalid_criteria_type(self) -> None:
        """Test that evaluators handle invalid criteria types properly."""
        config = {
            "name": "ErrorTest",
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )

        with pytest.raises(UiPathEvaluationError):
            # Try to validate invalid criteria
            evaluator.validate_evaluation_criteria("invalid_criteria")

    @pytest.mark.asyncio
    async def test_missing_config_fields(self, mocker: MockerFixture) -> None:
        """Test that evaluators properly validate config fields."""
        # Mock the UiPath constructor to avoid authentication
        mock_uipath = mocker.MagicMock()
        mocker.patch("uipath.UiPath", return_value=mock_uipath)

        config = {
            "name": "LLMJudgeEvaluator",
            "default_evaluation_criteria": {},
        }

        with pytest.raises(UiPathEvaluationError, match="Field required"):
            # Missing required field 'model'
            LLMJudgeOutputEvaluator.model_validate(
                {"config": config, "id": str(uuid.uuid4())}
            )


class TestEvaluationResultTypes:
    """Test that all evaluators return proper result types."""

    @pytest.mark.asyncio
    async def test_evaluators_return_results_with_scores(
        self, sample_agent_execution: AgentExecution
    ) -> None:
        """Test that evaluators return results with scores."""
        config = {
            "name": "Test",
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(expected_output={"output": "Test output"})  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        assert hasattr(result, "score")
        assert isinstance(result.score, (int, float))


class TestJustificationHandling:
    """Test justification handling in all evaluators."""

    @pytest.mark.asyncio
    async def test_exact_match_evaluator_justification(
        self, sample_agent_execution: AgentExecution
    ) -> None:
        """Test that ExactMatchEvaluator handles None justification correctly."""
        config = {
            "name": "ExactMatchTest",
            "case_sensitive": True,
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(expected_output={"output": "Test output"})  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        # Should be NumericEvaluationResult with no justification (None)
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0
        # Justification should be None for non-LLM evaluators
        assert (
            not hasattr(result, "justification")
            or getattr(result, "justification", None) is None
        )

    @pytest.mark.asyncio
    async def test_json_similarity_evaluator_justification(self) -> None:
        """Test that JsonSimilarityEvaluator handles None justification correctly."""
        execution = AgentExecution(
            agent_input={"input": "Test"},
            agent_output={"name": "John", "age": 30, "city": "NYC"},
            agent_trace=[],
        )
        config = {
            "name": "JsonSimilarityTest",
        }
        evaluator = JsonSimilarityEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(
            expected_output={"name": "John", "age": 30, "city": "NYC"}  # pyright: ignore[reportCallIssue]
        )

        result = await evaluator.evaluate(execution, criteria)

        # Should be NumericEvaluationResult with no justification (None)
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0
        # Justification should be None for non-LLM evaluators
        assert (
            not hasattr(result, "justification")
            or getattr(result, "justification", None) is None
        )

    @pytest.mark.asyncio
    async def test_tool_call_order_evaluator_justification(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test that ToolCallOrderEvaluator handles None justification correctly."""
        config = {
            "name": "ToolOrderTest",
            "strict": True,
        }
        evaluator = ToolCallOrderEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallOrderEvaluationCriteria(
            tool_calls_order=["tool1", "tool2", "tool1", "tool2"]
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        # Should be NumericEvaluationResult with no justification (None)
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0
        # Justification should be None for non-LLM evaluators
        assert (
            not hasattr(result, "justification")
            or getattr(result, "justification", None) is None
        )

    @pytest.mark.asyncio
    async def test_tool_call_count_evaluator_justification(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test that ToolCallCountEvaluator handles None justification correctly."""
        config = {
            "name": "ToolCountTest",
            "strict": True,
        }
        evaluator = ToolCallCountEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallCountEvaluationCriteria(
            tool_calls_count={"tool1": ("=", 2), "tool2": ("=", 2)}
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        # Should be NumericEvaluationResult with no justification (None)
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0
        # Justification should be None for non-LLM evaluators
        assert (
            not hasattr(result, "justification")
            or getattr(result, "justification", None) is None
        )

    @pytest.mark.asyncio
    async def test_tool_call_args_evaluator_justification(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test that ToolCallArgsEvaluator handles None justification correctly."""
        config = {
            "name": "ToolArgsTest",
            "strict": True,
        }
        evaluator = ToolCallArgsEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallArgsEvaluationCriteria(
            tool_calls=[
                ToolCall(name="tool1", args={"arg1": "value1"}),
                ToolCall(name="tool2", args={"arg2": "value2"}),
                ToolCall(name="tool1", args={"arg1": "value1"}),
                ToolCall(name="tool2", args={"arg2": "value2"}),
            ]
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        # Should be NumericEvaluationResult with no justification (None)
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0
        # Justification should be None for non-LLM evaluators
        assert (
            not hasattr(result, "justification")
            or getattr(result, "justification", None) is None
        )

    @pytest.mark.asyncio
    async def test_tool_call_output_evaluator_justification(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test that ToolCallOutputEvaluator handles justification correctly."""
        config = {
            "name": "ToolOutputTest",
            "strict": True,
        }
        evaluator = ToolCallOutputEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallOutputEvaluationCriteria(
            tool_outputs=[
                ToolOutput(name="tool1", output="output1"),
                ToolOutput(name="tool2", output="output2"),
                ToolOutput(name="tool1", output="output1"),
                ToolOutput(name="tool2", output="output2"),
            ]
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        # Should have justification with tool call output details
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0
        # The justification is stored in the details field for tool call evaluators
        assert hasattr(result, "details")
        assert isinstance(result.details, ToolCallOutputEvaluatorJustification)
        assert hasattr(result.details, "explained_tool_calls_outputs")
        assert isinstance(result.details.explained_tool_calls_outputs, dict)

    @pytest.mark.asyncio
    async def test_llm_judge_output_evaluator_justification(
        self, sample_agent_execution: AgentExecution, mocker: MockerFixture
    ) -> None:
        """Test that LLMJudgeOutputEvaluator handles str justification correctly."""
        # Mock the UiPath constructor to avoid authentication
        mock_uipath = mocker.MagicMock()
        mock_llm = mocker.MagicMock()
        mock_uipath.llm = mock_llm

        # Mock the chat completions response with justification
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 80, "justification": "The response meets most criteria but could be more detailed"}'
                )
            )
        ]

        # Make chat_completions an async method
        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        mock_llm.chat_completions = mock_chat_completions
        mocker.patch("uipath.UiPath", return_value=mock_uipath)

        config = {
            "name": "LlmJudgeTest",
            "prompt": "Rate this output: {{ActualOutput}} vs {{ExpectedOutput}}",
            "model": "gpt-4o-2024-08-06",
        }
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(expected_output="Expected output")  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        # Should have string justification in details field
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.8
        assert hasattr(result, "details")
        # The justification is stored in the details field for LLM evaluators
        assert isinstance(result.details, str)
        assert (
            result.details
            == "The response meets most criteria but could be more detailed"
        )

    @pytest.mark.asyncio
    async def test_llm_judge_trajectory_evaluator_justification(
        self, sample_agent_execution: AgentExecution, mocker: MockerFixture
    ) -> None:
        """Test that LLMJudgeTrajectoryEvaluator handles str justification correctly."""
        # Mock the UiPath constructor to avoid authentication
        mock_uipath = mocker.MagicMock()
        mock_llm = mocker.MagicMock()
        mock_uipath.llm = mock_llm

        # Mock the chat completions response with justification
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 85, "justification": "The agent trajectory shows good decision making and follows expected behavior patterns"}'
                )
            )
        ]

        # Make chat_completions an async method
        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        mock_llm.chat_completions = mock_chat_completions
        mocker.patch("uipath.UiPath", return_value=mock_uipath)

        config = {
            "name": "LlmTrajectoryTest",
            "prompt": "Evaluate this trajectory: {{AgentRunHistory}} vs {{ExpectedAgentBehavior}}",
            "model": "gpt-4",
        }
        evaluator = LLMJudgeTrajectoryEvaluator.model_validate(
            {"config": config, "id": str(uuid.uuid4())}
        )
        criteria = TrajectoryEvaluationCriteria(
            expected_agent_behavior="Agent should respond helpfully"
        )

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        # Should have string justification in details field (not justification attribute)
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.85
        assert isinstance(result.details, str)
        assert (
            result.details
            == "The agent trajectory shows good decision making and follows expected behavior patterns"
        )

    def test_justification_validation_edge_cases(self, mocker: MockerFixture) -> None:
        """Test edge cases for justification validation."""
        # Test None type evaluator
        config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        none_evaluator = ExactMatchEvaluator.model_validate(
            {"config": config_dict, "id": str(uuid.uuid4())}
        )

        # All inputs should return None for None type evaluators
        assert none_evaluator.validate_justification(None) is None
        assert none_evaluator.validate_justification("") is None
        assert none_evaluator.validate_justification("some text") is None
        assert none_evaluator.validate_justification(123) is None
        assert none_evaluator.validate_justification({"key": "value"}) is None

        # Test str type evaluator - need to provide llm_service to avoid authentication
        llm_config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
            "model": "gpt-4o-2024-08-06",
        }
        mock_llm_service = mocker.MagicMock()
        str_evaluator = LLMJudgeOutputEvaluator.model_validate(
            {
                "config": llm_config_dict,
                "llm_service": mock_llm_service,
                "id": str(uuid.uuid4()),
            }
        )

        # Different inputs should be converted to strings
        assert str_evaluator.validate_justification("test") == "test"
        assert str_evaluator.validate_justification("") == ""
        assert str_evaluator.validate_justification(123) == "123"
        assert str_evaluator.validate_justification(True) == "True"
        assert (
            str_evaluator.validate_justification(None) == ""
        )  # None becomes empty string

    def test_justification_type_extraction_all_evaluators(self) -> None:
        """Test that all evaluators have correct justification type extraction."""
        # Different evaluators have different justification types
        assert ExactMatchEvaluator._extract_justification_type() is type(
            None
        )  # No justification
        assert (
            JsonSimilarityEvaluator._extract_justification_type() is str
        )  # String justification

        # Tool call evaluators have their own justification types
        from uipath.eval.evaluators.tool_call_args_evaluator import (
            ToolCallArgsEvaluatorJustification,
        )
        from uipath.eval.evaluators.tool_call_count_evaluator import (
            ToolCallCountEvaluatorJustification,
        )
        from uipath.eval.evaluators.tool_call_order_evaluator import (
            ToolCallOrderEvaluatorJustification,
        )
        from uipath.eval.evaluators.tool_call_output_evaluator import (
            ToolCallOutputEvaluatorJustification,
        )

        assert (
            ToolCallOrderEvaluator._extract_justification_type()
            is ToolCallOrderEvaluatorJustification
        )
        assert (
            ToolCallCountEvaluator._extract_justification_type()
            is ToolCallCountEvaluatorJustification
        )
        assert (
            ToolCallArgsEvaluator._extract_justification_type()
            is ToolCallArgsEvaluatorJustification
        )
        assert (
            ToolCallOutputEvaluator._extract_justification_type()
            is ToolCallOutputEvaluatorJustification
        )

        # LLM evaluators should have str justification type
        assert LLMJudgeOutputEvaluator._extract_justification_type() is str
        assert LLMJudgeTrajectoryEvaluator._extract_justification_type() is str
