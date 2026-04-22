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

from uipath.eval.evaluators.base_evaluator import BaseEvaluatorJustification
from uipath.eval.evaluators.contains_evaluator import (
    ContainsEvaluationCriteria,
    ContainsEvaluator,
)
from uipath.eval.evaluators.exact_match_evaluator import ExactMatchEvaluator
from uipath.eval.evaluators.json_similarity_evaluator import (
    JsonSimilarityEvaluator,
    JsonSimilarityJustification,
)
from uipath.eval.evaluators.llm_as_judge_evaluator import LLMJudgeJustification
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
    ToolCallArgsEvaluatorJustification,
)
from uipath.eval.evaluators.tool_call_count_evaluator import (
    ToolCallCountEvaluationCriteria,
    ToolCallCountEvaluator,
    ToolCallCountEvaluatorJustification,
)
from uipath.eval.evaluators.tool_call_order_evaluator import (
    ToolCallOrderEvaluationCriteria,
    ToolCallOrderEvaluator,
    ToolCallOrderEvaluatorJustification,
)
from uipath.eval.evaluators.tool_call_output_evaluator import (
    ToolCallOutputEvaluationCriteria,
    ToolCallOutputEvaluator,
    ToolCallOutputEvaluatorJustification,
)
from uipath.eval.models import NumericEvaluationResult
from uipath_eval.models.models import (
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(
            expected_output={"output": "Test output"},  # pyright: ignore[reportCallIssue]
        )

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "actual_output, expected_output, expected_score",
        [
            # Scalar int/float normalization — the core fix
            (1, 1.0, 1.0),
            (1.0, 1, 1.0),
            (0, 0.0, 1.0),
            (-3, -3.0, 1.0),
            (1.5, 1, 0.0),
            (2, 3, 0.0),
        ],
    )
    async def test_exact_match_numeric_normalization(
        self, actual_output: Any, expected_output: Any, expected_score: float
    ) -> None:
        """Test that int and float scalar values are normalized before comparison."""
        execution = AgentExecution(
            agent_input={},
            agent_output={"value": actual_output},
            agent_trace=[],
        )
        config = {"name": "ExactMatchNumericTest", "target_output_key": "value"}
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(expected_output={"value": expected_output})  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == expected_score

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "actual_output, expected_output, target_key, expected_score",
        [
            # Flat dict: int vs float value
            ({"v": 1}, {"v": 1.0}, "*", 1.0),
            ({"v": 1.0}, {"v": 1}, "*", 1.0),
            ({"v": 1.5}, {"v": 1}, "*", 0.0),
            # Nested dict
            ({"a": {"b": 1}}, {"a": {"b": 1.0}}, "*", 1.0),
            ({"a": {"b": 1.5}}, {"a": {"b": 1}}, "*", 0.0),
            # List of numbers
            ({"vals": [1, 2, 3]}, {"vals": [1.0, 2.0, 3.0]}, "*", 1.0),
            ({"vals": [1, 2, 4]}, {"vals": [1.0, 2.0, 3.0]}, "*", 0.0),
            # target_output_key resolves to a dict containing int/float
            ({"result": {"count": 1}}, {"result": {"count": 1.0}}, "result", 1.0),
            # target_output_key resolves to a scalar int/float
            ({"result": 1}, {"result": 1.0}, "result", 1.0),
            ({"result": 1.5}, {"result": 1}, "result", 0.0),
        ],
    )
    async def test_exact_match_recursive_normalization(
        self,
        actual_output: Any,
        expected_output: Any,
        target_key: str,
        expected_score: float,
    ) -> None:
        """Test that int/float normalization works recursively for dicts, lists, and nested structures."""
        execution = AgentExecution(
            agent_input={},
            agent_output=actual_output,
            agent_trace=[],
        )
        config = {"name": "ExactMatchRecursiveTest", "target_output_key": target_key}
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(expected_output=expected_output)  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == expected_score

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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        raw_criteria = {"expected_output": {"output": "Test output"}}

        result = await evaluator.validate_and_evaluate_criteria(
            sample_agent_execution, raw_criteria
        )

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_exact_match_line_by_line_all_match(self) -> None:
        """Test line-by-line evaluation with all lines matching."""
        config = {
            "name": "ExactMatchLineByLineTest",
            "case_sensitive": False,
            "line_by_line_evaluator": True,
            "line_delimiter": "\n",
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )

        # Multi-line output
        agent_execution = AgentExecution(
            agent_input={"input": "Test input"},
            agent_output="line1\nline2\nline3",
            agent_trace=[],
        )
        criteria = OutputEvaluationCriteria(expected_output="line1\nline2\nline3")  # pyright: ignore[reportCallIssue]

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution, criteria
        )

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0  # All 3 lines match
        assert result.details is not None
        assert hasattr(result.details, "line_by_line_results")
        assert hasattr(result.details, "total_lines_actual")
        assert hasattr(result.details, "total_lines_expected")
        assert result.details.total_lines_actual == 3
        assert result.details.total_lines_expected == 3
        assert len(result.details.line_by_line_results) == 3

    @pytest.mark.asyncio
    async def test_exact_match_line_by_line_partial_match(self) -> None:
        """Test line-by-line evaluation with some lines not matching."""
        config = {
            "name": "ExactMatchLineByLineTest",
            "case_sensitive": False,
            "line_by_line_evaluator": True,
            "line_delimiter": "\n",
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )

        # Multi-line output with 2 out of 3 lines matching
        agent_execution = AgentExecution(
            agent_input={"input": "Test input"},
            agent_output="line1\nwrong\nline3",
            agent_trace=[],
        )
        criteria = OutputEvaluationCriteria(expected_output="line1\nline2\nline3")  # pyright: ignore[reportCallIssue]

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution, criteria
        )

        assert isinstance(result, NumericEvaluationResult)
        # 2 out of 3 lines match = 0.666...
        assert math.isclose(result.score, 2.0 / 3.0, rel_tol=0.01)
        assert result.details is not None
        assert hasattr(result.details, "line_by_line_results")
        assert len(result.details.line_by_line_results) == 3
        # Check first line matches
        assert result.details.line_by_line_results[0].score == 1.0
        # Check second line doesn't match
        assert result.details.line_by_line_results[1].score == 0.0
        # Check third line matches
        assert result.details.line_by_line_results[2].score == 1.0

    @pytest.mark.asyncio
    async def test_exact_match_line_by_line_custom_delimiter(self) -> None:
        """Test line-by-line evaluation with custom delimiter."""
        config = {
            "name": "ExactMatchLineByLineTest",
            "case_sensitive": False,
            "line_by_line_evaluator": True,
            "line_delimiter": "|",
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )

        # Pipe-delimited output
        agent_execution = AgentExecution(
            agent_input={"input": "Test input"},
            agent_output="part1|part2|part3",
            agent_trace=[],
        )
        criteria = OutputEvaluationCriteria(expected_output="part1|part2|part3")  # pyright: ignore[reportCallIssue]

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution, criteria
        )

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0
        assert result.details is not None
        assert hasattr(result.details, "line_by_line_results")
        assert len(result.details.line_by_line_results) == 3

    @pytest.mark.asyncio
    async def test_exact_match_line_by_line_has_individual_results(self) -> None:
        """Test that line-by-line evaluation attaches individual line results."""
        config = {
            "name": "ExactMatchLineByLineTest",
            "case_sensitive": False,
            "line_by_line_evaluator": True,
            "line_delimiter": "\n",
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )

        # Multi-line output with 2 out of 3 lines matching
        agent_execution = AgentExecution(
            agent_input={"input": "Test input"},
            agent_output="line1\nwrong\nline3",
            agent_trace=[],
        )
        criteria = OutputEvaluationCriteria(expected_output="line1\nline2\nline3")  # pyright: ignore[reportCallIssue]

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution, criteria
        )

        # Check that the result has the _line_by_line_results attribute
        assert hasattr(result, "_line_by_line_results")
        line_by_line_container = result._line_by_line_results

        # Verify we have 3 individual line results
        assert len(line_by_line_container.line_results) == 3

        # Check each line result
        line1_num, line1_result = line_by_line_container.line_results[0]
        assert line1_num == 1
        assert line1_result.score == 1.0

        line2_num, line2_result = line_by_line_container.line_results[1]
        assert line2_num == 2
        assert line2_result.score == 0.0

        line3_num, line3_result = line_by_line_container.line_results[2]
        assert line3_num == 3
        assert line3_result.score == 1.0


class TestContainsEvaluator:
    """Test ContainsEvaluator.evaluate() method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "agent_output, search_text, target_key, case_sensitive, negated, expected_score",
        [
            # Basic match
            ("Test output", "Test output", "*", False, False, 1.0),
            # Substring match
            ("Hello World", "World", "*", False, False, 1.0),
            # No match
            ("Hello World", "Goodbye", "*", False, False, 0.0),
            # Case-insensitive match (default)
            ("Hello World", "hello world", "*", False, False, 1.0),
            # Case-sensitive hit
            ("Hello World", "Hello", "*", True, False, 1.0),
            # Case-sensitive miss
            ("Hello World", "hello", "*", True, False, 0.0),
            # Negated hit becomes miss
            ("Test output", "Test output", "*", False, True, 0.0),
            # Negated miss becomes hit
            ("Hello World", "Goodbye", "*", False, True, 1.0),
            # target_output_key extraction
            ("Test output", "Test output", "output", False, False, 1.0),
        ],
    )
    async def test_contains_evaluator(
        self,
        agent_output: Any,
        search_text: str,
        target_key: str,
        case_sensitive: bool,
        negated: bool,
        expected_score: float,
        sample_agent_execution: AgentExecution,
    ) -> None:
        """Test ContainsEvaluator across match, no-match, case sensitivity, and negation cases."""
        if target_key == "output":
            execution = (
                sample_agent_execution  # has agent_output={"output": "Test output"}
            )
        else:
            execution = AgentExecution(
                agent_input={},
                agent_output=agent_output,
                agent_trace=[],
            )
        config = {
            "name": "ContainsTest",
            "target_output_key": target_key,
            "case_sensitive": case_sensitive,
            "negated": negated,
        }
        evaluator = ContainsEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = ContainsEvaluationCriteria(search_text=search_text)
        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == expected_score

    @pytest.mark.asyncio
    async def test_contains_evaluator_validate_and_evaluate_criteria(
        self, sample_agent_execution: AgentExecution
    ) -> None:
        """Test contains evaluator with validate_and_evaluate_criteria."""
        config = {
            "name": "ContainsTest",
            "target_output_key": "*",
        }
        evaluator = ContainsEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(
            expected_output={"name": "John", "age": 30, "city": "NYC"}  # pyright: ignore[reportCallIssue]
        )

        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert math.isclose(result.score, 0.666, abs_tol=1e-3)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "actual_output, expected_output, expected_score",
        [
            # int/float normalization — identical after normalization
            ({"count": 1}, {"count": 1.0}, 1.0),
            ({"count": 1.0}, {"count": 1}, 1.0),
            # Nested int/float
            ({"a": {"b": 1}}, {"a": {"b": 1.0}}, 1.0),
            # List of ints vs floats
            ({"vals": [1, 2, 3]}, {"vals": [1.0, 2.0, 3.0]}, 1.0),
            # Different numeric values — partial score: 1.0 - |expected-actual|/|expected|
            ({"count": 1.5}, {"count": 1}, 0.5),
        ],
    )
    async def test_json_similarity_numeric_normalization(
        self,
        actual_output: Any,
        expected_output: Any,
        expected_score: float,
    ) -> None:
        """Test that int/float normalization is applied before JSON similarity comparison."""
        execution = AgentExecution(
            agent_input={},
            agent_output=actual_output,
            agent_trace=[],
        )
        config = {"name": "JsonSimilarityTest"}
        evaluator = JsonSimilarityEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(expected_output=expected_output)  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == expected_score

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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
        """Test LLM as judge basic evaluation functionality with function calling."""
        mock_tool_call = mocker.MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "submit_evaluation"
        mock_tool_call.arguments = {
            "score": 80,
            "justification": "Good response that meets criteria",
        }

        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(content=None, tool_calls=[mock_tool_call])
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        mock_llm_instance = mocker.MagicMock()
        mock_llm_instance.chat_completions = mock_chat_completions

        mocker.patch("uipath.eval.evaluators.llm_as_judge_evaluator.UiPath")
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.UiPathLlmChatService",
            return_value=mock_llm_instance,
        )

        config = {
            "name": "LlmJudgeTest",
            "prompt": "Rate this output: {{ActualOutput}} vs {{ExpectedOutput}}",
            "model": "gpt-4o-2024-08-06",
        }
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
        """Test LLM judge basic evaluation functionality with a custom LLM service and function calling."""
        # Mock tool call for function calling approach
        mock_tool_call = mocker.MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "submit_evaluation"
        mock_tool_call.arguments = {
            "score": 80,
            "justification": "Good response that meets criteria",
        }

        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(content=None, tool_calls=[mock_tool_call])
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
                "evaluatorConfig": config,
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
        """Test LLM judge using validate_and_evaluate_criteria with function calling."""
        mock_tool_call = mocker.MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "submit_evaluation"
        mock_tool_call.arguments = {
            "score": 75,
            "justification": "Good response using raw criteria",
        }

        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(content=None, tool_calls=[mock_tool_call])
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        mock_llm_instance = mocker.MagicMock()
        mock_llm_instance.chat_completions = mock_chat_completions

        mocker.patch("uipath.eval.evaluators.llm_as_judge_evaluator.UiPath")
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.UiPathLlmChatService",
            return_value=mock_llm_instance,
        )

        config = {
            "name": "LlmJudgeTest",
            "prompt": "Rate this output: {{ActualOutput}} vs {{ExpectedOutput}}",
            "model": "gpt-4",
        }
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
        """Test LLM trajectory judge basic evaluation functionality with function calling."""
        mock_tool_call = mocker.MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "submit_evaluation"
        mock_tool_call.arguments = {
            "score": 90,
            "justification": "The agent followed the expected behavior and met the criteria",
        }

        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(content=None, tool_calls=[mock_tool_call])
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        mock_llm_instance = mocker.MagicMock()
        mock_llm_instance.chat_completions = mock_chat_completions

        mocker.patch("uipath.eval.evaluators.llm_as_judge_evaluator.UiPath")
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.UiPathLlmChatService",
            return_value=mock_llm_instance,
        )

        config = {
            "name": "LlmTrajectoryTest",
            "prompt": "Evaluate this trajectory: {{AgentRunHistory}} vs {{ExpectedAgentBehavior}} given the following input: {{UserOrSyntheticInput}} instructions: {{SimulationInstructions}}",
            "model": "gpt-4",
        }
        evaluator = LLMJudgeTrajectoryEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
        """Test LLM trajectory judge using validate_and_evaluate_criteria with function calling."""
        mock_tool_call = mocker.MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "submit_evaluation"
        mock_tool_call.arguments = {
            "score": 85,
            "justification": "The agent behavior was good using raw criteria",
        }

        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(content=None, tool_calls=[mock_tool_call])
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        mock_llm_instance = mocker.MagicMock()
        mock_llm_instance.chat_completions = mock_chat_completions

        mocker.patch("uipath.eval.evaluators.llm_as_judge_evaluator.UiPath")
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.UiPathLlmChatService",
            return_value=mock_llm_instance,
        )

        config = {
            "name": "LlmTrajectoryTest",
            "prompt": "Evaluate this trajectory: {{AgentRunHistory}} vs {{ExpectedAgentBehavior}} given the following input: {{UserOrSyntheticInput}} instructions: {{SimulationInstructions}}",
            "model": "gpt-4",
        }
        evaluator = LLMJudgeTrajectoryEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )

        with pytest.raises(UiPathEvaluationError):
            # Try to validate invalid criteria
            evaluator.validate_evaluation_criteria("invalid_criteria")

    @pytest.mark.asyncio
    async def test_missing_config_fields(self, mocker: MockerFixture) -> None:
        """Test that evaluators properly validate config fields."""
        # Mock the UiPath constructor to avoid authentication
        mock_uipath = mocker.MagicMock()
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.UiPath",
            return_value=mock_uipath,
        )

        config = {
            "name": "LLMJudgeEvaluator",
            "default_evaluation_criteria": {},
        }

        with pytest.raises(UiPathEvaluationError):
            # Invalid default_evaluation_criteria (missing expectedOutput)
            LLMJudgeOutputEvaluator.model_validate(
                {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
        """Test that ExactMatchEvaluator provides BaseEvaluatorJustification."""

        config = {
            "name": "ExactMatchTest",
            "case_sensitive": True,
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(expected_output={"output": "Test output"})  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0
        assert isinstance(result.details, BaseEvaluatorJustification)
        assert result.details.expected is not None
        assert result.details.actual is not None

    @pytest.mark.asyncio
    async def test_json_similarity_evaluator_justification(self) -> None:
        """Test that JsonSimilarityEvaluator provides JsonSimilarityJustification."""

        execution = AgentExecution(
            agent_input={"input": "Test"},
            agent_output={"name": "John", "age": 30, "city": "NYC"},
            agent_trace=[],
        )
        config = {
            "name": "JsonSimilarityTest",
        }
        evaluator = JsonSimilarityEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(
            expected_output={"name": "John", "age": 30, "city": "NYC"}  # pyright: ignore[reportCallIssue]
        )

        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0
        assert isinstance(result.details, JsonSimilarityJustification)
        assert result.details.matched_leaves == 3.0
        assert result.details.total_leaves == 3.0

    @pytest.mark.asyncio
    async def test_tool_call_order_evaluator_justification(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test that ToolCallOrderEvaluator provides structured justification."""

        config = {
            "name": "ToolOrderTest",
            "strict": True,
        }
        evaluator = ToolCallOrderEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallOrderEvaluationCriteria(
            tool_calls_order=["tool1", "tool2", "tool1", "tool2"]
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0
        assert isinstance(result.details, ToolCallOrderEvaluatorJustification)

    @pytest.mark.asyncio
    async def test_tool_call_count_evaluator_justification(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test that ToolCallCountEvaluator provides structured justification."""

        config = {
            "name": "ToolCountTest",
            "strict": True,
        }
        evaluator = ToolCallCountEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = ToolCallCountEvaluationCriteria(
            tool_calls_count={"tool1": ("=", 2), "tool2": ("=", 2)}
        )

        result = await evaluator.evaluate(sample_agent_execution_with_trace, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0
        assert isinstance(result.details, ToolCallCountEvaluatorJustification)

    @pytest.mark.asyncio
    async def test_tool_call_args_evaluator_justification(
        self, sample_agent_execution_with_trace: AgentExecution
    ) -> None:
        """Test that ToolCallArgsEvaluator provides structured justification."""

        config = {
            "name": "ToolArgsTest",
            "strict": True,
        }
        evaluator = ToolCallArgsEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
        assert isinstance(result.details, ToolCallArgsEvaluatorJustification)

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
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
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
        """Test that LLMJudgeOutputEvaluator handles str justification correctly with function calling."""
        mock_tool_call = mocker.MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "submit_evaluation"
        mock_tool_call.arguments = {
            "score": 80,
            "justification": "The response meets most criteria but could be more detailed",
        }

        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(content=None, tool_calls=[mock_tool_call])
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        mock_llm_instance = mocker.MagicMock()
        mock_llm_instance.chat_completions = mock_chat_completions

        mocker.patch("uipath.eval.evaluators.llm_as_judge_evaluator.UiPath")
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.UiPathLlmChatService",
            return_value=mock_llm_instance,
        )

        config = {
            "name": "LlmJudgeTest",
            "prompt": "Rate this output: {{ActualOutput}} vs {{ExpectedOutput}}",
            "model": "gpt-4o-2024-08-06",
        }
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = OutputEvaluationCriteria(expected_output="Expected output")  # pyright: ignore[reportCallIssue]

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        # Should have LLMJudgeJustification in details field

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.8
        assert hasattr(result, "details")
        # The justification is stored in the details field for LLM evaluators
        assert isinstance(result.details, LLMJudgeJustification)
        assert (
            result.details.justification
            == "The response meets most criteria but could be more detailed"
        )

    @pytest.mark.asyncio
    async def test_llm_judge_trajectory_evaluator_justification(
        self, sample_agent_execution: AgentExecution, mocker: MockerFixture
    ) -> None:
        """Test that LLMJudgeTrajectoryEvaluator handles str justification correctly."""
        mock_tool_call = mocker.MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "submit_evaluation"
        mock_tool_call.arguments = {
            "score": 85,
            "justification": "The agent trajectory shows good decision making and follows expected behavior patterns",
        }

        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(content=None, tool_calls=[mock_tool_call])
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        mock_llm_instance = mocker.MagicMock()
        mock_llm_instance.chat_completions = mock_chat_completions

        mocker.patch("uipath.eval.evaluators.llm_as_judge_evaluator.UiPath")
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.UiPathLlmChatService",
            return_value=mock_llm_instance,
        )

        config = {
            "name": "LlmTrajectoryTest",
            "prompt": "Evaluate this trajectory: {{AgentRunHistory}} vs {{ExpectedAgentBehavior}}",
            "model": "gpt-4",
        }
        evaluator = LLMJudgeTrajectoryEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = TrajectoryEvaluationCriteria(
            expected_agent_behavior="Agent should respond helpfully"
        )

        result = await evaluator.evaluate(sample_agent_execution, criteria)

        # Should have LLMJudgeJustification in details field

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.85
        assert isinstance(result.details, LLMJudgeJustification)
        assert (
            result.details.justification
            == "The agent trajectory shows good decision making and follows expected behavior patterns"
        )

    def test_justification_validation_edge_cases(self, mocker: MockerFixture) -> None:
        """Test edge cases for justification validation."""

        # Test BaseEvaluatorJustification type evaluator
        config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        output_evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": config_dict, "id": str(uuid.uuid4())}
        )

        # Valid BaseEvaluatorJustification should pass through
        justification = BaseEvaluatorJustification(expected="expected", actual="actual")
        result = output_evaluator.validate_justification(justification)
        assert isinstance(result, BaseEvaluatorJustification)
        assert result.expected == "expected"

        # Dict should be validated into BaseEvaluatorJustification
        result = output_evaluator.validate_justification(
            {"expected": "exp", "actual": "act"}
        )
        assert isinstance(result, BaseEvaluatorJustification)
        assert result.expected == "exp"

        # Test LLMJudgeJustification type evaluator - need to provide llm_service to avoid authentication

        llm_config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
            "model": "gpt-4o-2024-08-06",
        }
        mock_llm_service = mocker.MagicMock()
        llm_evaluator = LLMJudgeOutputEvaluator.model_validate(
            {
                "evaluatorConfig": llm_config_dict,
                "llm_service": mock_llm_service,
                "id": str(uuid.uuid4()),
            }
        )

        # LLMJudgeJustification validation
        llm_justification = LLMJudgeJustification(
            expected="expected", actual="actual", justification="test"
        )
        llm_result = llm_evaluator.validate_justification(llm_justification)
        assert isinstance(llm_result, LLMJudgeJustification)
        assert llm_result.justification == "test"

    def test_justification_type_extraction_all_evaluators(self) -> None:
        """Test that all evaluators have correct justification type extraction."""

        # Different evaluators have different justification types
        assert (
            ExactMatchEvaluator._extract_justification_type()
            is BaseEvaluatorJustification
        )
        assert (
            JsonSimilarityEvaluator._extract_justification_type()
            is JsonSimilarityJustification
        )

        # Tool call evaluators have their own justification types
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

        # LLM evaluators should have LLMJudgeJustification justification type
        assert (
            LLMJudgeOutputEvaluator._extract_justification_type()
            is LLMJudgeJustification
        )
        assert (
            LLMJudgeTrajectoryEvaluator._extract_justification_type()
            is LLMJudgeJustification
        )

    @pytest.mark.asyncio
    async def test_llm_judge_omits_max_tokens_when_none(
        self, sample_agent_execution: AgentExecution, mocker: MockerFixture
    ) -> None:
        """Test that max_tokens is omitted from API request when None (fixes 400 error)."""
        mock_tool_call = mocker.MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "submit_evaluation"
        mock_tool_call.arguments = {
            "score": 80,
            "justification": "Good response",
        }

        mock_message = mocker.MagicMock()
        mock_message.tool_calls = [mock_tool_call]
        mock_message.content = None

        mock_choice = mocker.MagicMock()
        mock_choice.message = mock_message

        mock_response = mocker.MagicMock()
        mock_response.choices = [mock_choice]

        captured_request = {}

        async def capture_chat_completions(**kwargs: Any) -> Any:
            nonlocal captured_request
            captured_request = kwargs
            return mock_response

        mock_llm_instance = mocker.MagicMock()
        mock_llm_instance.chat_completions = capture_chat_completions

        mocker.patch("uipath.eval.evaluators.llm_as_judge_evaluator.UiPath")
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.UiPathLlmChatService",
            return_value=mock_llm_instance,
        )

        config = {
            "name": "TestMaxTokensNone",
            "model": "gpt-4o-mini-2024-07-18",
            "prompt": "Evaluate the output",
        }
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )

        result = await evaluator.evaluate(
            agent_execution=sample_agent_execution,
            evaluation_criteria=OutputEvaluationCriteria(expected_output="42"),
        )

        assert "max_tokens" not in captured_request, (
            "max_tokens should be omitted when None, not passed as None "
            "(this was causing 400 errors from LLM Gateway API)"
        )

        assert "model" in captured_request
        assert "temperature" in captured_request
        assert "tools" in captured_request
        assert "tool_choice" in captured_request
        assert "messages" in captured_request

        assert result.score == 0.8
        assert isinstance(result.details, LLMJudgeJustification)
        assert result.details.justification == "Good response"


class TestClaude45ModelSupport:
    """Tests for Claude 4.5 model-specific behavior in LLM evaluators.

    Claude 4.5 models (Haiku, Sonnet) require special handling:
    - max_tokens must be set (defaults to 8000 when not configured)
    - Function calling (tools/tool_choice) is used for structured output
    - OpenAI-specific parameters (n, frequency_penalty, etc.) must NOT be sent
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "model_name",
        [
            "anthropic.claude-haiku-4-5-20251001-v1:0",
            "anthropic.claude-sonnet-4-5-20250929-v1:0",
        ],
    )
    async def test_claude_45_evaluator_uses_function_calling(
        self,
        model_name: str,
        sample_agent_execution: AgentExecution,
        mocker: MockerFixture,
    ) -> None:
        """Test that Claude 4.5 evaluators use function calling (tools/tool_choice)."""
        mock_tool_call = mocker.MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "submit_evaluation"
        mock_tool_call.arguments = {
            "score": 95,
            "justification": "Perfect match",
        }

        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(content=None, tool_calls=[mock_tool_call])
            )
        ]

        captured_request: dict[str, Any] = {}

        async def capture_chat_completions(**kwargs: Any) -> Any:
            nonlocal captured_request
            captured_request = kwargs
            return mock_response

        mock_llm_instance = mocker.MagicMock()
        mock_llm_instance.chat_completions = capture_chat_completions

        mocker.patch("uipath.eval.evaluators.llm_as_judge_evaluator.UiPath")
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.UiPathLlmChatService",
            return_value=mock_llm_instance,
        )

        config = {
            "name": f"Claude45Test-{model_name}",
            "prompt": "Rate this output: {{ActualOutput}} vs {{ExpectedOutput}}",
            "model": model_name,
        }
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )

        criteria = OutputEvaluationCriteria(expected_output="Expected output")  # pyright: ignore[reportCallIssue]
        result = await evaluator.evaluate(sample_agent_execution, criteria)

        # Verify function calling is used
        assert "tools" in captured_request, (
            "Claude 4.5 models must use function calling"
        )
        assert "tool_choice" in captured_request, (
            "tool_choice must be set for Claude 4.5"
        )
        assert captured_request["model"] == model_name

        # Verify result is correct
        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.95
        assert isinstance(result.details, LLMJudgeJustification)
        assert result.details.justification == "Perfect match"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "model_name",
        [
            "anthropic.claude-haiku-4-5-20251001-v1:0",
            "anthropic.claude-sonnet-4-5-20250929-v1:0",
        ],
    )
    async def test_claude_45_sets_default_max_tokens(
        self,
        model_name: str,
        sample_agent_execution: AgentExecution,
        mocker: MockerFixture,
    ) -> None:
        """Test that Claude 4.5 models get default max_tokens=8000 when not configured."""
        mock_tool_call = mocker.MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "submit_evaluation"
        mock_tool_call.arguments = {"score": 80, "justification": "Good"}

        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(content=None, tool_calls=[mock_tool_call])
            )
        ]

        captured_request: dict[str, Any] = {}

        async def capture_chat_completions(**kwargs: Any) -> Any:
            nonlocal captured_request
            captured_request = kwargs
            return mock_response

        mock_llm_instance = mocker.MagicMock()
        mock_llm_instance.chat_completions = capture_chat_completions

        mocker.patch("uipath.eval.evaluators.llm_as_judge_evaluator.UiPath")
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.UiPathLlmChatService",
            return_value=mock_llm_instance,
        )

        # No max_tokens in config - should default to 8000 for Claude 4.5
        config = {
            "name": f"Claude45MaxTokensTest-{model_name}",
            "prompt": "Rate: {{ActualOutput}} vs {{ExpectedOutput}}",
            "model": model_name,
        }
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )

        criteria = OutputEvaluationCriteria(expected_output="Expected")  # pyright: ignore[reportCallIssue]
        await evaluator.evaluate(sample_agent_execution, criteria)

        assert "max_tokens" in captured_request, (
            "Claude 4.5 models require max_tokens to be set"
        )
        assert captured_request["max_tokens"] == 8000, (
            "Default max_tokens for Claude 4.5 should be 8000"
        )

    @pytest.mark.asyncio
    async def test_claude_45_respects_configured_max_tokens(
        self,
        sample_agent_execution: AgentExecution,
        mocker: MockerFixture,
    ) -> None:
        """Test that explicitly configured max_tokens overrides the Claude 4.5 default."""
        mock_tool_call = mocker.MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "submit_evaluation"
        mock_tool_call.arguments = {"score": 80, "justification": "Good"}

        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(content=None, tool_calls=[mock_tool_call])
            )
        ]

        captured_request: dict[str, Any] = {}

        async def capture_chat_completions(**kwargs: Any) -> Any:
            nonlocal captured_request
            captured_request = kwargs
            return mock_response

        mock_llm_instance = mocker.MagicMock()
        mock_llm_instance.chat_completions = capture_chat_completions

        mocker.patch("uipath.eval.evaluators.llm_as_judge_evaluator.UiPath")
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.UiPathLlmChatService",
            return_value=mock_llm_instance,
        )

        config = {
            "name": "Claude45CustomMaxTokens",
            "prompt": "Rate: {{ActualOutput}} vs {{ExpectedOutput}}",
            "model": "anthropic.claude-haiku-4-5-20251001-v1:0",
            "maxTokens": 4096,
        }
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )

        criteria = OutputEvaluationCriteria(expected_output="Expected")  # pyright: ignore[reportCallIssue]
        await evaluator.evaluate(sample_agent_execution, criteria)

        assert captured_request["max_tokens"] == 4096, (
            "Configured max_tokens should override the Claude 4.5 default"
        )


class TestBinaryClassificationEvaluator:
    """Test BinaryClassificationEvaluator.evaluate() method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "predicted, expected_class, positive_class, expected_score",
        [
            # TP: pred=positive, exp=positive → match → 1.0
            ("spam", "spam", "spam", 1.0),
            # FP: pred=positive, exp=negative → mismatch → 0.0
            ("spam", "ham", "spam", 0.0),
            # FN: pred=negative, exp=positive → mismatch → 0.0
            ("ham", "spam", "spam", 0.0),
            # TN: pred=negative, exp=negative → match → 1.0
            ("ham", "ham", "spam", 1.0),
            # Case insensitive TP
            ("Spam", "SPAM", "spam", 1.0),
        ],
    )
    async def test_binary_classification_scoring(
        self,
        predicted: str,
        expected_class: str,
        positive_class: str,
        expected_score: float,
    ) -> None:
        """Test BinaryClassificationEvaluator returns 1.0 for match, 0.0 for mismatch."""
        from uipath.eval.evaluators.binary_classification_evaluator import (
            BinaryClassificationEvaluationCriteria,
            BinaryClassificationEvaluator,
        )

        execution = AgentExecution(
            agent_input={},
            agent_output={"class": predicted},
            agent_trace=[],
        )
        config = {
            "name": "BinaryClassificationTest",
            "target_output_key": "class",
            "positive_class": positive_class,
        }
        evaluator = BinaryClassificationEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = BinaryClassificationEvaluationCriteria(
            expected_class=expected_class,
        )
        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == expected_score
        assert isinstance(result.details, BaseEvaluatorJustification)


class TestMulticlassClassificationEvaluator:
    """Test MulticlassClassificationEvaluator.evaluate() method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "predicted, expected_class, classes, expected_score",
        [
            # Correct prediction → 1.0
            ("cat", "cat", ["cat", "dog", "bird"], 1.0),
            # Mismatch → 0.0
            ("dog", "cat", ["cat", "dog", "bird"], 0.0),
            # Mismatch → 0.0
            ("cat", "dog", ["cat", "dog", "bird"], 0.0),
            # Correct prediction → 1.0
            ("bird", "bird", ["cat", "dog", "bird"], 1.0),
            # Case insensitive match → 1.0
            ("Cat", "CAT", ["cat", "dog", "bird"], 1.0),
        ],
    )
    async def test_multiclass_classification_scoring(
        self,
        predicted: str,
        expected_class: str,
        classes: list[str],
        expected_score: float,
    ) -> None:
        """Test MulticlassClassificationEvaluator returns 1.0 for match, 0.0 for mismatch."""
        from uipath.eval.evaluators.multiclass_classification_evaluator import (
            MulticlassClassificationEvaluationCriteria,
            MulticlassClassificationEvaluator,
        )

        execution = AgentExecution(
            agent_input={},
            agent_output={"class": predicted},
            agent_trace=[],
        )
        config = {
            "name": "MulticlassClassificationTest",
            "target_output_key": "class",
            "classes": classes,
        }
        evaluator = MulticlassClassificationEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = MulticlassClassificationEvaluationCriteria(
            expected_class=expected_class,
        )
        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == expected_score
        assert isinstance(result.details, BaseEvaluatorJustification)

    @pytest.mark.asyncio
    async def test_multiclass_classification_invalid_expected_class(self) -> None:
        """Test that an invalid expected class returns an error result."""
        from uipath.eval.evaluators.multiclass_classification_evaluator import (
            MulticlassClassificationEvaluationCriteria,
            MulticlassClassificationEvaluator,
        )
        from uipath.eval.models.models import ErrorEvaluationResult

        execution = AgentExecution(
            agent_input={},
            agent_output={"class": "cat"},
            agent_trace=[],
        )
        config = {
            "name": "MulticlassClassificationTest",
            "target_output_key": "class",
            "classes": ["cat", "dog"],
        }
        evaluator = MulticlassClassificationEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = MulticlassClassificationEvaluationCriteria(expected_class="bird")
        result = await evaluator.evaluate(execution, criteria)
        assert isinstance(result, ErrorEvaluationResult)
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_multiclass_classification_invalid_predicted_class(self) -> None:
        """Test that an invalid predicted class returns an error result."""
        from uipath.eval.evaluators.multiclass_classification_evaluator import (
            MulticlassClassificationEvaluationCriteria,
            MulticlassClassificationEvaluator,
        )
        from uipath.eval.models.models import ErrorEvaluationResult

        execution = AgentExecution(
            agent_input={},
            agent_output={"class": "fish"},
            agent_trace=[],
        )
        config = {
            "name": "MulticlassClassificationTest",
            "target_output_key": "class",
            "classes": ["cat", "dog"],
        }
        evaluator = MulticlassClassificationEvaluator.model_validate(
            {"evaluatorConfig": config, "id": str(uuid.uuid4())}
        )
        criteria = MulticlassClassificationEvaluationCriteria(expected_class="cat")
        result = await evaluator.evaluate(execution, criteria)
        assert isinstance(result, ErrorEvaluationResult)
        assert result.score == 0.0
