"""Tests for examples in the eval documentation.

This module ensures all code examples in the documentation actually work by
testing them with proper agent execution data. For LLM judge examples, we use
mocked completions to avoid API calls.
"""

from typing import Any

import pytest
from pytest_mock.plugin import MockerFixture

from uipath.eval.evaluators import (
    ContainsEvaluator,
    ExactMatchEvaluator,
    JsonSimilarityEvaluator,
    LLMJudgeOutputEvaluator,
    LLMJudgeTrajectoryEvaluator,
)
from uipath.eval.evaluators.tool_call_order_evaluator import (
    ToolCallOrderEvaluatorJustification,
)
from uipath.eval.models import AgentExecution


class TestIndexExamples:
    """Test examples from docs/eval/index.md."""

    @pytest.mark.asyncio
    async def test_getting_started_example(self) -> None:
        """Test the getting started example from index.md."""
        from uipath.eval.evaluators import ExactMatchEvaluator

        # Sample agent execution (this is what the docs were missing!)
        agent_execution = AgentExecution(
            agent_input={"query": "Greet the world"},
            agent_output={"result": "hello, world!"},
            agent_trace=[],
        )

        # Create evaluator
        evaluator = ExactMatchEvaluator(  # type: ignore[call-arg]
            id="exact-match-1",
            config={
                "name": "ExactMatchEvaluator",
                "case_sensitive": False,
                "target_output_key": "result",
            },
        )

        # Evaluate
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={"expected_output": {"result": "Hello, World!"}},
        )

        assert result.score == 1.0


class TestContainsExamples:
    """Test examples from docs/eval/contains.md."""

    @pytest.mark.asyncio
    async def test_basic_usage(self) -> None:
        """Test basic usage example."""
        from uipath.eval.evaluators import ContainsEvaluator
        from uipath.eval.models import AgentExecution

        # Create evaluator - extracts "response" field for comparison
        evaluator = ContainsEvaluator(  # type: ignore[call-arg]
            id="contains-check",
            config={
                "name": "ContainsEvaluator",
                "case_sensitive": False,
                "target_output_key": "response",  # Extract the "response" field
            },
        )

        # agent_output must be a dict
        agent_execution = AgentExecution(
            agent_input={"query": "What is the capital of France?"},
            agent_output={"response": "The capital of France is Paris."},
            agent_trace=[],
        )

        # Evaluate - searches in the "response" field value
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={"search_text": "Paris"},
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_case_sensitive_search(self) -> None:
        """Test case-sensitive search example."""
        evaluator = ContainsEvaluator(  # type: ignore[call-arg]
            id="contains-case-sensitive",
            config={
                "name": "ContainsEvaluator",
                "case_sensitive": True,
                "target_output_key": "message",  # Extract the "message" field
            },
        )

        agent_execution = AgentExecution(
            agent_input={},
            agent_output={"message": "Hello World"},
            agent_trace=[],
        )

        # This will fail because of case mismatch
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={"search_text": "hello"},
        )

        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_negated_search(self) -> None:
        """Test negated search example."""
        evaluator = ContainsEvaluator(  # type: ignore[call-arg]
            id="contains-negated",
            config={
                "name": "ContainsEvaluator",
                "negated": True,
                "target_output_key": "status",  # Extract the "status" field
            },
        )

        agent_execution = AgentExecution(
            agent_input={},
            agent_output={"status": "Success: Operation completed"},
            agent_trace=[],
        )

        # Passes because "error" is NOT found
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={"search_text": "error"},
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_target_specific_output_field(self) -> None:
        """Test targeting specific output field example."""
        evaluator = ContainsEvaluator(  # type: ignore[call-arg]
            id="contains-targeted",
            config={"name": "ContainsEvaluator", "target_output_key": "message"},
        )

        agent_execution = AgentExecution(
            agent_input={},
            agent_output={
                "status": "success",
                "message": "User profile updated successfully",
            },
            agent_trace=[],
        )

        # Only searches within the "message" field
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={"search_text": "updated"},
        )

        assert result.score == 1.0


class TestExactMatchExamples:
    """Test examples from docs/eval/exact_match.md."""

    @pytest.mark.asyncio
    async def test_basic_usage(self) -> None:
        """Test basic usage example."""
        from uipath.eval.evaluators import ExactMatchEvaluator
        from uipath.eval.models import AgentExecution

        # agent_output must be a dict
        agent_execution = AgentExecution(
            agent_input={"query": "What is 2+2?"},
            agent_output={"result": "4"},
            agent_trace=[],
        )

        # Create evaluator - extracts "result" field for comparison
        evaluator = ExactMatchEvaluator(  # type: ignore[call-arg]
            id="exact-match-1",
            config={
                "name": "ExactMatchEvaluator",
                "case_sensitive": False,
                "target_output_key": "result",  # Extract the "result" field
            },
        )

        # Evaluate - compares just the "result" field value
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={"expected_output": {"result": "4"}},
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_case_sensitive_matching(self) -> None:
        """Test case-sensitive matching example."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_output={"status": "SUCCESS"},
            agent_trace=[],
        )

        evaluator = ExactMatchEvaluator(  # type: ignore[call-arg]
            id="exact-match-case",
            config={
                "name": "ExactMatchEvaluator",
                "case_sensitive": True,
                "target_output_key": "status",  # Extract the "status" field
            },
        )

        # Fails due to case mismatch
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={"expected_output": {"status": "success"}},
        )

        assert result.score == 0.0

        # This would pass
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={"expected_output": {"status": "SUCCESS"}},
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_matching_structured_outputs(self) -> None:
        """Test matching structured outputs example."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_output={"status": "success", "code": 200},
            agent_trace=[],
        )

        evaluator = ExactMatchEvaluator(  # type: ignore[call-arg]
            id="exact-match-dict",
            config={
                "name": "ExactMatchEvaluator",
                "target_output_key": "*",  # Compare entire output (default)
            },
        )

        # Entire dict structure must match
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={"expected_output": {"status": "success", "code": 200}},
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_negated_mode(self) -> None:
        """Test negated mode example."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_output={"result": "error"},
            agent_trace=[],
        )

        evaluator = ExactMatchEvaluator(  # type: ignore[call-arg]
            id="exact-match-negated",
            config={
                "name": "ExactMatchEvaluator",
                "negated": True,
                "target_output_key": "result",  # Extract the "result" field
            },
        )

        # Passes because outputs do NOT match
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={"expected_output": {"result": "success"}},
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_using_default_criteria(self) -> None:
        """Test using default criteria example."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_output={"status": "OK"},
            agent_trace=[],
        )

        evaluator = ExactMatchEvaluator(  # type: ignore[call-arg]
            id="exact-match-default",
            config={
                "name": "ExactMatchEvaluator",
                "target_output_key": "status",  # Extract the "status" field
                "default_evaluation_criteria": {"expected_output": {"status": "OK"}},
            },
        )

        # Use default criteria
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution, evaluation_criteria=None
        )

        assert result.score == 1.0


class TestJsonSimilarityExamples:
    """Test examples from docs/eval/json_similarity.md."""

    @pytest.mark.asyncio
    async def test_basic_json_comparison(self) -> None:
        """Test basic JSON comparison example."""
        from uipath.eval.evaluators import JsonSimilarityEvaluator
        from uipath.eval.models import AgentExecution

        agent_execution = AgentExecution(
            agent_input={},
            agent_output={"name": "John Doe", "age": 30, "city": "New York"},
            agent_trace=[],
        )

        evaluator = JsonSimilarityEvaluator(  # type: ignore[call-arg]
            id="json-sim-1",
            config={
                "name": "JsonSimilarityEvaluator"
                # target_output_key defaults to "*" - compares entire output dict
            },
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "expected_output": {"name": "John Doe", "age": 30, "city": "New York"}
            },
        )

        assert result.score == 1.0
        # The details format may include .0 for integer values
        assert isinstance(result.details, str)
        assert (
            "Matched leaves: 3" in result.details
            and "Total leaves: 3" in result.details
        )

    @pytest.mark.asyncio
    async def test_numeric_tolerance(self) -> None:
        """Test numeric tolerance example."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_output={"temperature": 20.5, "humidity": 65},
            agent_trace=[],
        )

        evaluator = JsonSimilarityEvaluator(  # type: ignore[call-arg]
            id="json-sim-numeric",
            config={"name": "JsonSimilarityEvaluator"},
        )

        # Slightly different numbers
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "expected_output": {"temperature": 20.3, "humidity": 65}
            },
        )

        # High similarity despite numeric difference
        assert result.score >= 0.9

    @pytest.mark.asyncio
    async def test_string_similarity(self) -> None:
        """Test string similarity example."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_output={"status": "completed successfully"},
            agent_trace=[],
        )

        evaluator = JsonSimilarityEvaluator(  # type: ignore[call-arg]
            id="json-sim-string",
            config={"name": "JsonSimilarityEvaluator"},
        )

        # Similar but not exact string
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "expected_output": {"status": "completed sucessfully"}  # typo
            },
        )

        # High but not perfect similarity
        assert result.score >= 0.9
        assert result.score < 1.0

    @pytest.mark.asyncio
    async def test_nested_structures(self) -> None:
        """Test nested structures example."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_output={
                "user": {"name": "Alice", "profile": {"age": 25, "location": "Paris"}},
                "status": "active",
            },
            agent_trace=[],
        )

        evaluator = JsonSimilarityEvaluator(  # type: ignore[call-arg]
            id="json-sim-nested",
            config={"name": "JsonSimilarityEvaluator"},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "expected_output": {
                    "user": {
                        "name": "Alice",
                        "profile": {"age": 25, "location": "Paris"},
                    },
                    "status": "active",
                }
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_array_comparison(self) -> None:
        """Test array comparison example."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_output={"items": ["apple", "banana", "orange"]},
            agent_trace=[],
        )

        evaluator = JsonSimilarityEvaluator(  # type: ignore[call-arg]
            id="json-sim-array",
            config={"name": "JsonSimilarityEvaluator"},
        )

        # Partial match (2 out of 3 correct)
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "expected_output": {"items": ["apple", "banana", "grape"]}
            },
        )

        # The actual implementation gives partial credit for string similarity
        # "orange" vs "grape" has some similarity, so score is higher than simple 2/3
        assert 0.75 <= result.score <= 0.85

    @pytest.mark.asyncio
    async def test_handling_extra_keys(self) -> None:
        """Test handling extra keys in actual output example."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_output={
                "name": "Bob",
                "age": 30,
                "extra_field": "ignored",  # Extra field in actual output
            },
            agent_trace=[],
        )

        evaluator = JsonSimilarityEvaluator(  # type: ignore[call-arg]
            id="json-sim-extra",
            config={"name": "JsonSimilarityEvaluator"},
        )

        # Only expected keys are evaluated
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={"expected_output": {"name": "Bob", "age": 30}},
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_target_specific_field(self) -> None:
        """Test target specific field example."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_output={
                "result": {"score": 95, "passed": True},
                "metadata": {"timestamp": "2024-01-01"},
            },
            agent_trace=[],
        )

        evaluator = JsonSimilarityEvaluator(  # type: ignore[call-arg]
            id="json-sim-targeted",
            config={
                "name": "JsonSimilarityEvaluator",
                "target_output_key": "result",
            },
        )

        # Only compares the "result" field
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "expected_output": {"result": {"score": 95, "passed": True}}
            },
        )

        assert result.score == 1.0


class TestLLMJudgeOutputExamples:
    """Test examples from docs/eval/llm_judge_output.md."""

    @pytest.mark.asyncio
    async def test_basic_semantic_similarity(self, mocker: MockerFixture) -> None:
        """Test basic semantic similarity example."""
        from uipath.eval.evaluators import LLMJudgeOutputEvaluator
        from uipath.eval.models import AgentExecution

        # Mock the LLM response
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 95, "justification": "Both outputs convey the same meaning about Paris being the capital of France."}'
                )
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        agent_execution = AgentExecution(
            agent_input={"query": "What is the capital of France?"},
            agent_output={"answer": "Paris is the capital city of France."},
            agent_trace=[],
        )

        evaluator = LLMJudgeOutputEvaluator(  # type: ignore[call-arg]
            id="llm-judge-1",
            config={
                "name": "LLMJudgeOutputEvaluator",
                "model": "gpt-4",
                "temperature": 0.0,
                "target_output_key": "answer",  # Extract the "answer" field
            },
            llm_service=mock_chat_completions,
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "expected_output": {"answer": "The capital of France is Paris."}
            },
        )

        assert result.score == 0.95

    @pytest.mark.asyncio
    async def test_custom_evaluation_prompt(self, mocker: MockerFixture) -> None:
        """Test custom evaluation prompt example."""
        # Mock the LLM response
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 90, "justification": "Both messages convey successful cart addition."}'
                )
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        custom_prompt = """
Compare the actual output with the expected output.
Focus on semantic meaning and intent rather than exact wording.

Actual Output: {{ActualOutput}}
Expected Output: {{ExpectedOutput}}

Provide a score from 0-100 based on semantic similarity.
"""

        agent_execution = AgentExecution(
            agent_input={},
            agent_output={
                "message": "The product has been successfully added to your cart."
            },
            agent_trace=[],
        )

        evaluator = LLMJudgeOutputEvaluator(  # type: ignore[call-arg]
            id="llm-judge-custom",
            config={
                "name": "LLMJudgeOutputEvaluator",
                "model": "gpt-4",
                "prompt": custom_prompt,
                "temperature": 0.0,
                "target_output_key": "message",  # Extract the "message" field
            },
            llm_service=mock_chat_completions,
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "expected_output": {"message": "Item added to shopping cart."}
            },
        )

        assert result.score == 0.9

    @pytest.mark.asyncio
    async def test_evaluating_natural_language_quality(
        self, mocker: MockerFixture
    ) -> None:
        """Test evaluating natural language quality example."""
        # Mock the LLM response
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 85, "justification": "The email is professional and addresses the customer inquiry appropriately."}'
                )
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        agent_execution = AgentExecution(
            agent_input={"task": "Write a professional email"},
            agent_output={
                "email": """Dear Customer,

Thank you for your inquiry. We have reviewed your request
and are pleased to inform you that we can accommodate your
needs. Please let us know if you have any questions.

Best regards,
Support Team"""
            },
            agent_trace=[],
        )

        evaluator = LLMJudgeOutputEvaluator(  # type: ignore[call-arg]
            id="llm-judge-quality",
            config={
                "name": "LLMJudgeOutputEvaluator",
                "model": "gpt-4o",
                "temperature": 0.0,
                "target_output_key": "email",  # Extract the "email" field
            },
            llm_service=mock_chat_completions,
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "expected_output": {
                    "email": "A professional, courteous response addressing the customer's inquiry"
                }
            },
        )

        assert result.score == 0.85

    @pytest.mark.asyncio
    async def test_strict_json_similarity(self, mocker: MockerFixture) -> None:
        """Test strict JSON similarity output evaluator example."""
        from uipath.eval.evaluators import (
            LLMJudgeStrictJSONSimilarityOutputEvaluator,
        )

        # Mock the LLM response
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 100, "justification": "All keys match perfectly."}'
                )
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        agent_execution = AgentExecution(
            agent_input={},
            agent_output={
                "status": "success",
                "user_id": 12345,
                "name": "John Doe",
                "email": "john@example.com",
            },
            agent_trace=[],
        )

        evaluator = LLMJudgeStrictJSONSimilarityOutputEvaluator(  # type: ignore[call-arg]
            id="llm-json-strict",
            config={
                "name": "LLMJudgeStrictJSONSimilarityOutputEvaluator",
                "model": "gpt-4",
                "temperature": 0.0,
            },
            llm_service=mock_chat_completions,
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "expected_output": {
                    "status": "success",
                    "user_id": 12345,
                    "name": "John Doe",
                    "email": "john@example.com",
                }
            },
        )

        assert result.score == 1.0


class TestLLMJudgeTrajectoryExamples:
    """Test examples from docs/eval/llm_judge_trajectory.md."""

    @pytest.mark.asyncio
    async def test_basic_trajectory_evaluation(self, mocker: MockerFixture) -> None:
        """Test basic trajectory evaluation example."""
        from uipath.eval.evaluators import LLMJudgeTrajectoryEvaluator
        from uipath.eval.models import AgentExecution

        # Mock the LLM response
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 85, "justification": "Agent followed the expected booking flow."}'
                )
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        agent_execution = AgentExecution(
            agent_input={"user_query": "Book a flight to Paris"},
            agent_output={"booking_id": "FL123", "status": "confirmed"},
            agent_trace=[
                # Trace contains spans showing the agent's execution path
                # Each span represents a step in the agent's decision-making
            ],
        )

        evaluator = LLMJudgeTrajectoryEvaluator(  # type: ignore[call-arg]
            id="trajectory-judge-1",
            config={
                "name": "LLMJudgeTrajectoryEvaluator",
                "model": "gpt-4",
                "temperature": 0.0,
            },
            llm_service=mock_chat_completions,
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "expected_agent_behavior": """
        The agent should:
        1. Search for available flights to Paris
        2. Present options to the user
        3. Process the booking
        4. Confirm the reservation
        """
            },
        )

        assert result.score == 0.85

    @pytest.mark.asyncio
    async def test_validating_tool_usage_sequence(self, mocker: MockerFixture) -> None:
        """Test validating tool usage sequence example."""
        # Mock the LLM response
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 90, "justification": "Agent correctly validated, updated, and notified in proper sequence."}'
                )
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        agent_execution = AgentExecution(
            agent_input={"task": "Update user profile and send notification"},
            agent_output={"status": "completed"},
            agent_trace=[
                # Spans showing: validate_user -> update_profile -> send_notification
            ],
        )

        evaluator = LLMJudgeTrajectoryEvaluator(  # type: ignore[call-arg]
            id="trajectory-tools",
            config={
                "name": "LLMJudgeTrajectoryEvaluator",
                "model": "gpt-4o",
                "temperature": 0.0,
            },
            llm_service=mock_chat_completions,
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "expected_agent_behavior": """
        The agent must:
        1. First validate the user exists
        2. Update the profile in the database
        3. Send a confirmation notification
        This sequence must be followed to ensure data integrity.
        """
            },
        )

        assert result.score == 0.9

    @pytest.mark.asyncio
    async def test_trajectory_simulation(self, mocker: MockerFixture) -> None:
        """Test tool simulation trajectory evaluation example."""
        from uipath.eval.evaluators import LLMJudgeTrajectorySimulationEvaluator

        # Mock the LLM response
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 88, "justification": "Agent followed expected flow with simulated tool responses."}'
                )
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        agent_execution = AgentExecution(
            agent_input={"query": "Book a flight to Paris for tomorrow"},
            agent_output={"booking_id": "FL123", "status": "confirmed"},
            agent_trace=[
                # Execution spans showing tool calls and their simulated responses
            ],
            simulation_instructions="""
    Simulate the following tool responses:
    - search_flights tool: Return 3 available flights with prices
    - book_flight tool: Return booking confirmation with ID "FL123"
    - send_confirmation_email tool: Return success status
    Mock the tools to respond as if it's a Tuesday in March with normal availability.
    """,
        )

        evaluator = LLMJudgeTrajectorySimulationEvaluator(  # type: ignore[call-arg]
            id="sim-trajectory-1",
            config={
                "name": "LLMJudgeTrajectorySimulationEvaluator",
                "model": "gpt-4",
                "temperature": 0.0,
            },
            llm_service=mock_chat_completions,
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "expected_agent_behavior": """
        The agent should:
        1. Call search_flights to find available options
        2. Present flight options to the user (simulated in conversation)
        3. Call book_flight with appropriate parameters
        4. Confirm the booking with the user
        5. Call send_confirmation_email to notify the user
        """
            },
        )

        assert result.score == 0.88


# Note: Tool call evaluators (order, count, args, output) require proper trace data with tool calls
# These are more complex to set up and are already well-tested in test_evaluator_methods.py
# The documentation examples for these assume the trace is already populated with tool call spans.
# Since creating realistic trace data with tool calls is complex and implementation-specific,
# we'll add simplified versions of key examples.


class TestToolCallOrderExamples:
    """Test examples from docs/eval/tool_call_order.md."""

    @pytest.mark.asyncio
    async def test_basic_tool_call_order(self) -> None:
        """Test basic tool call order validation example with sample trace."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallOrderEvaluator

        # Sample agent execution with tool calls in trace (this is what was missing in docs!)
        mock_spans = [
            ReadableSpan(
                name="validate_user",
                start_time=0,
                end_time=1,
                attributes={"tool.name": "validate_user"},
            ),
            ReadableSpan(
                name="check_inventory",
                start_time=1,
                end_time=2,
                attributes={"tool.name": "check_inventory"},
            ),
            ReadableSpan(
                name="create_order",
                start_time=2,
                end_time=3,
                attributes={"tool.name": "create_order"},
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Process user order"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallOrderEvaluator(  # type: ignore[call-arg]
            id="order-check-1",
            config={"name": "ToolCallOrderEvaluator", "strict": False},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls_order": ["validate_user", "check_inventory", "create_order"]
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_strict_order_validation(self) -> None:
        """Test strict order validation example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallOrderEvaluator

        # Critical security sequence
        mock_spans = [
            ReadableSpan(
                name="authenticate_user",
                start_time=0,
                end_time=1,
                attributes={"tool.name": "authenticate_user"},
            ),
            ReadableSpan(
                name="verify_permissions",
                start_time=1,
                end_time=2,
                attributes={"tool.name": "verify_permissions"},
            ),
            ReadableSpan(
                name="access_resource",
                start_time=2,
                end_time=3,
                attributes={"tool.name": "access_resource"},
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Access secured resource"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallOrderEvaluator(  # type: ignore[call-arg]
            id="order-strict",
            config={"name": "ToolCallOrderEvaluator", "strict": True},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls_order": [
                    "authenticate_user",
                    "verify_permissions",
                    "access_resource",
                ]
            },
        )

        # Score is either 1.0 (perfect match) or 0.0 (any mismatch)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_partial_credit_with_lcs(self) -> None:
        """Test partial credit with LCS example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallOrderEvaluator

        # Actual execution (missing "sort")
        mock_spans = [
            ReadableSpan(
                name="search",
                start_time=0,
                end_time=1,
                attributes={"tool.name": "search"},
            ),
            ReadableSpan(
                name="filter",
                start_time=1,
                end_time=2,
                attributes={"tool.name": "filter"},
            ),
            ReadableSpan(
                name="display",
                start_time=2,
                end_time=3,
                attributes={"tool.name": "display"},
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Search and display"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallOrderEvaluator(  # type: ignore[call-arg]
            id="order-lcs",
            config={"name": "ToolCallOrderEvaluator", "strict": False},
        )

        # Expected sequence
        expected = ["search", "filter", "sort", "display"]

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={"tool_calls_order": expected},
        )

        # Score: 3/4 = 0.75 (3 tools in correct order out of 4 expected)
        assert result.score == 0.75
        assert isinstance(result.details, ToolCallOrderEvaluatorJustification)
        assert result.details.lcs == ["search", "filter", "display"]

    @pytest.mark.asyncio
    async def test_database_transaction_sequence(self) -> None:
        """Test database transaction sequence example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallOrderEvaluator

        mock_spans = [
            ReadableSpan(
                name="begin_transaction",
                start_time=0,
                end_time=1,
                attributes={"tool.name": "begin_transaction"},
            ),
            ReadableSpan(
                name="validate_data",
                start_time=1,
                end_time=2,
                attributes={"tool.name": "validate_data"},
            ),
            ReadableSpan(
                name="update_records",
                start_time=2,
                end_time=3,
                attributes={"tool.name": "update_records"},
            ),
            ReadableSpan(
                name="commit_transaction",
                start_time=3,
                end_time=4,
                attributes={"tool.name": "commit_transaction"},
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Update database"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallOrderEvaluator(  # type: ignore[call-arg]
            id="db-transaction",
            config={"name": "ToolCallOrderEvaluator", "strict": True},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls_order": [
                    "begin_transaction",
                    "validate_data",
                    "update_records",
                    "commit_transaction",
                ]
            },
        )

        # Must match exactly for data integrity
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_api_integration_workflow(self) -> None:
        """Test API integration workflow example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallOrderEvaluator

        mock_spans = [
            ReadableSpan(
                name="get_api_token",
                start_time=0,
                end_time=1,
                attributes={"tool.name": "get_api_token"},
            ),
            ReadableSpan(
                name="fetch_user_data",
                start_time=1,
                end_time=2,
                attributes={"tool.name": "fetch_user_data"},
            ),
            ReadableSpan(
                name="enrich_data",
                start_time=2,
                end_time=3,
                attributes={"tool.name": "enrich_data"},
            ),
            ReadableSpan(
                name="post_to_webhook",
                start_time=3,
                end_time=4,
                attributes={"tool.name": "post_to_webhook"},
            ),
            ReadableSpan(
                name="log_result",
                start_time=4,
                end_time=5,
                attributes={"tool.name": "log_result"},
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "API integration"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallOrderEvaluator(  # type: ignore[call-arg]
            id="api-workflow",
            config={"name": "ToolCallOrderEvaluator", "strict": False},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls_order": [
                    "get_api_token",
                    "fetch_user_data",
                    "enrich_data",
                    "post_to_webhook",
                    "log_result",
                ]
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_using_default_criteria(self) -> None:
        """Test using default criteria example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallOrderEvaluator

        mock_spans = [
            ReadableSpan(
                name="init",
                start_time=0,
                end_time=1,
                attributes={"tool.name": "init"},
            ),
            ReadableSpan(
                name="process",
                start_time=1,
                end_time=2,
                attributes={"tool.name": "process"},
            ),
            ReadableSpan(
                name="cleanup",
                start_time=2,
                end_time=3,
                attributes={"tool.name": "cleanup"},
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Standard workflow"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallOrderEvaluator(  # type: ignore[call-arg]
            id="order-default",
            config={
                "name": "ToolCallOrderEvaluator",
                "strict": False,
                "default_evaluation_criteria": {
                    "tool_calls_order": ["init", "process", "cleanup"]
                },
            },
        )

        # Use default criteria
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution, evaluation_criteria=None
        )

        assert result.score == 1.0


class TestToolCallCountExamples:
    """Test examples from docs/eval/tool_call_count.md."""

    @pytest.mark.asyncio
    async def test_basic_count_validation(self) -> None:
        """Test basic count validation example with sample trace."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallCountEvaluator

        # Sample agent execution with tool calls (this is what was missing in docs!)
        mock_spans = [
            ReadableSpan(
                name="fetch_data",
                start_time=0,
                end_time=1,
                attributes={"tool.name": "fetch_data"},
            ),
            ReadableSpan(
                name="process_item",
                start_time=1,
                end_time=2,
                attributes={"tool.name": "process_item"},
            ),
            ReadableSpan(
                name="process_item",
                start_time=2,
                end_time=3,
                attributes={"tool.name": "process_item"},
            ),
            ReadableSpan(
                name="process_item",
                start_time=3,
                end_time=4,
                attributes={"tool.name": "process_item"},
            ),
            ReadableSpan(
                name="process_item",
                start_time=4,
                end_time=5,
                attributes={"tool.name": "process_item"},
            ),
            ReadableSpan(
                name="process_item",
                start_time=5,
                end_time=6,
                attributes={"tool.name": "process_item"},
            ),
            ReadableSpan(
                name="send_notification",
                start_time=6,
                end_time=7,
                attributes={"tool.name": "send_notification"},
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Fetch and process data"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallCountEvaluator(  # type: ignore[call-arg]
            id="count-check-1",
            config={"name": "ToolCallCountEvaluator", "strict": False},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls_count": {
                    "fetch_data": ("=", 1),
                    "process_item": ("=", 5),
                    "send_notification": ("=", 1),
                }
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_using_comparison_operators(self) -> None:
        """Test using comparison operators example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallCountEvaluator

        mock_spans = [
            ReadableSpan(
                name="validate",
                start_time=0,
                end_time=1,
                attributes={"tool.name": "validate"},
            ),
            ReadableSpan(
                name="retry_api",
                start_time=1,
                end_time=2,
                attributes={"tool.name": "retry_api"},
            ),
            ReadableSpan(
                name="log_event",
                start_time=2,
                end_time=3,
                attributes={"tool.name": "log_event"},
            ),
            ReadableSpan(
                name="expensive_call",
                start_time=3,
                end_time=4,
                attributes={"tool.name": "expensive_call"},
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "API operation"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallCountEvaluator(  # type: ignore[call-arg]
            id="count-operators",
            config={"name": "ToolCallCountEvaluator", "strict": False},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls_count": {
                    "validate": (">=", 1),  # At least once
                    "retry_api": ("<=", 3),  # At most 3 times
                    "log_event": (">", 0),  # More than 0 times
                    "expensive_call": ("<", 2),  # Less than 2 times
                }
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_strict_mode_all_or_nothing(self) -> None:
        """Test strict mode - all or nothing example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallCountEvaluator

        mock_spans = [
            ReadableSpan(
                name="authenticate",
                start_time=0,
                end_time=1,
                attributes={"tool.name": "authenticate"},
            ),
            ReadableSpan(
                name="fetch_records",
                start_time=1,
                end_time=2,
                attributes={"tool.name": "fetch_records"},
            ),
            ReadableSpan(
                name="close_connection",
                start_time=2,
                end_time=3,
                attributes={"tool.name": "close_connection"},
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Database operation"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallCountEvaluator(  # type: ignore[call-arg]
            id="count-strict",
            config={"name": "ToolCallCountEvaluator", "strict": True},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls_count": {
                    "authenticate": ("=", 1),
                    "fetch_records": ("=", 1),
                    "close_connection": ("=", 1),
                }
            },
        )

        # Score is 1.0 only if ALL counts match exactly
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_preventing_redundant_calls(self) -> None:
        """Test preventing redundant calls example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallCountEvaluator

        # Only one expensive call
        mock_spans = [
            ReadableSpan(
                name="expensive_api_call",
                start_time=0,
                end_time=1,
                attributes={"tool.name": "expensive_api_call"},
            ),
            ReadableSpan(
                name="database_query",
                start_time=1,
                end_time=2,
                attributes={"tool.name": "database_query"},
            ),
            ReadableSpan(
                name="database_query",
                start_time=2,
                end_time=3,
                attributes={"tool.name": "database_query"},
            ),
            ReadableSpan(
                name="llm_call",
                start_time=3,
                end_time=4,
                attributes={"tool.name": "llm_call"},
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Optimize resource usage"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallCountEvaluator(  # type: ignore[call-arg]
            id="prevent-redundant",
            config={"name": "ToolCallCountEvaluator", "strict": False},
        )

        # Ensure expensive operations aren't called too many times
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls_count": {
                    "expensive_api_call": (
                        "<=",
                        1,
                    ),  # Should not be called more than once
                    "database_query": ("<=", 3),  # At most 3 queries
                    "llm_call": ("<=", 2),  # At most 2 LLM calls
                }
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_loop_validation(self) -> None:
        """Test loop validation example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallCountEvaluator

        # Create 10 process_item, 10 validate_item, 10 save_result calls
        mock_spans = []
        for i in range(10):
            mock_spans.extend(
                [
                    ReadableSpan(
                        name="process_item",
                        start_time=i * 3,
                        end_time=i * 3 + 1,
                        attributes={"tool.name": "process_item"},
                    ),
                    ReadableSpan(
                        name="validate_item",
                        start_time=i * 3 + 1,
                        end_time=i * 3 + 2,
                        attributes={"tool.name": "validate_item"},
                    ),
                    ReadableSpan(
                        name="save_result",
                        start_time=i * 3 + 2,
                        end_time=i * 3 + 3,
                        attributes={"tool.name": "save_result"},
                    ),
                ]
            )

        agent_execution = AgentExecution(
            agent_input={"task": "Process 10 items"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallCountEvaluator(  # type: ignore[call-arg]
            id="loop-validation",
            config={"name": "ToolCallCountEvaluator", "strict": False},
        )

        # Verify loop processed correct number of items
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls_count": {
                    "process_item": ("=", 10),  # Should process 10 items
                    "validate_item": ("=", 10),  # Each item should be validated
                    "save_result": ("=", 10),  # Each result should be saved
                }
            },
        )

        assert result.score == 1.0


class TestToolCallArgsExamples:
    """Test examples from docs/eval/tool_call_args.md."""

    @pytest.mark.asyncio
    async def test_basic_argument_validation(self) -> None:
        """Test basic argument validation example with sample trace."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallArgsEvaluator

        # Sample agent execution with tool calls and arguments (this is what was missing in docs!)
        mock_spans = [
            ReadableSpan(
                name="update_user",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "update_user",
                    "input.value": "{'user_id': 123, 'fields': {'email': 'user@example.com'}, 'notify': True}",
                },
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"user_id": 123, "action": "update"},
            agent_output={"status": "success"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallArgsEvaluator(  # type: ignore[call-arg]
            id="args-check-1",
            config={
                "name": "ToolCallArgsEvaluator",
                "strict": False,
                "subset": False,
            },
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls": [
                    {
                        "name": "update_user",
                        "args": {
                            "user_id": 123,
                            "fields": {"email": "user@example.com"},
                            "notify": True,
                        },
                    }
                ]
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_strict_mode_exact_matching(self) -> None:
        """Test strict mode - exact matching example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallArgsEvaluator

        mock_spans = [
            ReadableSpan(
                name="send_email",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "send_email",
                    "input.value": "{'to': 'user@example.com', 'subject': 'Hello', 'body': 'Test message'}",
                },
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Send email"},
            agent_output={"status": "sent"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallArgsEvaluator(  # type: ignore[call-arg]
            id="args-strict",
            config={"name": "ToolCallArgsEvaluator", "strict": True, "subset": False},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls": [
                    {
                        "name": "send_email",
                        "args": {
                            "to": "user@example.com",
                            "subject": "Hello",
                            "body": "Test message",
                        },
                    }
                ]
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_subset_mode_partial_validation(self) -> None:
        """Test subset mode - partial validation example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallArgsEvaluator

        mock_spans = [
            ReadableSpan(
                name="create_user",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "create_user",
                    "input.value": "{'username': 'john_doe', 'email': 'john@example.com', 'role': 'admin', 'active': True}",
                },
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Create user"},
            agent_output={"status": "created"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallArgsEvaluator(  # type: ignore[call-arg]
            id="args-subset",
            config={"name": "ToolCallArgsEvaluator", "strict": False, "subset": True},
        )

        # Only validate critical fields
        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls": [
                    {
                        "name": "create_user",
                        "args": {"username": "john_doe", "email": "john@example.com"},
                    }
                ]
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self) -> None:
        """Test multiple tool calls example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallArgsEvaluator

        mock_spans = [
            ReadableSpan(
                name="fetch_data",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "fetch_data",
                    "input.value": "{'source': 'database', 'query': 'SELECT * FROM users'}",
                },
            ),
            ReadableSpan(
                name="process_data",
                start_time=1,
                end_time=2,
                attributes={
                    "tool.name": "process_data",
                    "input.value": "{'data': [{'id': 1}], 'operation': 'filter'}",
                },
            ),
            ReadableSpan(
                name="save_results",
                start_time=2,
                end_time=3,
                attributes={
                    "tool.name": "save_results",
                    "input.value": "{'destination': 'cache', 'ttl': 3600}",
                },
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Data pipeline"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallArgsEvaluator(  # type: ignore[call-arg]
            id="args-multiple",
            config={"name": "ToolCallArgsEvaluator", "strict": False, "subset": False},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls": [
                    {
                        "name": "fetch_data",
                        "args": {"source": "database", "query": "SELECT * FROM users"},
                    },
                    {
                        "name": "process_data",
                        "args": {"data": [{"id": 1}], "operation": "filter"},
                    },
                    {
                        "name": "save_results",
                        "args": {"destination": "cache", "ttl": 3600},
                    },
                ]
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_nested_arguments(self) -> None:
        """Test nested arguments example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallArgsEvaluator

        mock_spans = [
            ReadableSpan(
                name="configure_service",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "configure_service",
                    "input.value": "{'service': 'api', 'config': {'host': 'api.example.com', 'port': 443, 'ssl': {'enabled': True, 'cert_path': '/path/to/cert'}}}",
                },
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Configure API service"},
            agent_output={"status": "configured"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallArgsEvaluator(  # type: ignore[call-arg]
            id="args-nested",
            config={"name": "ToolCallArgsEvaluator", "strict": False, "subset": False},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls": [
                    {
                        "name": "configure_service",
                        "args": {
                            "service": "api",
                            "config": {
                                "host": "api.example.com",
                                "port": 443,
                                "ssl": {"enabled": True, "cert_path": "/path/to/cert"},
                            },
                        },
                    }
                ]
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_non_strict_proportional_scoring(self) -> None:
        """Test non-strict mode with proportional scoring (2/3 tools match)."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallArgsEvaluator
        from uipath.eval.models import AgentExecution

        # Agent called 3 tools, but only 2 match the expected args
        mock_spans = [
            ReadableSpan(
                name="validate_input",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "validate_input",
                    "input.value": "{'data': {'user_id': 123}}",  # ✓ Matches
                },
            ),
            ReadableSpan(
                name="fetch_user",
                start_time=1,
                end_time=2,
                attributes={
                    "tool.name": "fetch_user",
                    "input.value": "{'user_id': 999}",  # ✗ Wrong ID!
                },
            ),
            ReadableSpan(
                name="update_profile",
                start_time=2,
                end_time=3,
                attributes={
                    "tool.name": "update_profile",
                    "input.value": "{'user_id': 123, 'updates': {'name': 'John Doe'}}",  # ✓ Matches
                },
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Update user profile"},
            agent_output={"status": "updated"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallArgsEvaluator(  # type: ignore[call-arg]
            id="args-proportional",
            config={
                "name": "ToolCallArgsEvaluator",
                "strict": False,  # Proportional scoring
                "subset": False,
            },
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_calls": [
                    {
                        "name": "validate_input",
                        "args": {"data": {"user_id": 123}},  # ✓ Matches
                    },
                    {
                        "name": "fetch_user",
                        "args": {"user_id": 123},  # ✗ Actual was 999
                    },
                    {
                        "name": "update_profile",
                        "args": {
                            "user_id": 123,
                            "updates": {"name": "John Doe"},  # ✓ Matches
                        },
                    },
                ]
            },
        )

        # Score is 2/3 = 0.66 (2 out of 3 tools matched)
        assert abs(result.score - 0.66) < 0.01  # Allow small floating point differences


class TestToolCallOutputExamples:
    """Test examples from docs/eval/tool_call_output.md."""

    @pytest.mark.asyncio
    async def test_basic_output_validation(self) -> None:
        """Test basic output validation example with sample trace."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallOutputEvaluator

        # Sample agent execution with tool calls and outputs (this is what was missing in docs!)
        mock_spans = [
            ReadableSpan(
                name="get_user",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "get_user",
                    "output.value": '{"content": "{\\"user_id\\": 123, \\"name\\": \\"John Doe\\", \\"email\\": \\"john@example.com\\", \\"status\\": \\"active\\"}"}',
                },
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"user_id": 123},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallOutputEvaluator(  # type: ignore[call-arg]
            id="output-check-1",
            config={"name": "ToolCallOutputEvaluator", "strict": False},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_outputs": [
                    {
                        "name": "get_user",
                        "output": '{"user_id": 123, "name": "John Doe", "email": "john@example.com", "status": "active"}',
                    }
                ]
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_strict_mode_exact_output_matching(self) -> None:
        """Test strict mode - exact output matching example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallOutputEvaluator

        mock_spans = [
            ReadableSpan(
                name="calculate",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "calculate",
                    "output.value": '{"content": "{\\"result\\": 42, \\"operation\\": \\"multiply\\"}"}',
                },
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"operation": "multiply"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallOutputEvaluator(  # type: ignore[call-arg]
            id="output-strict",
            config={"name": "ToolCallOutputEvaluator", "strict": True},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_outputs": [
                    {
                        "name": "calculate",
                        "output": '{"result": 42, "operation": "multiply"}',
                    }
                ]
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_multiple_tool_outputs(self) -> None:
        """Test multiple tool outputs example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallOutputEvaluator

        mock_spans = [
            ReadableSpan(
                name="fetch",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "fetch",
                    "output.value": '{"content": "{\\"data\\": [\\"item1\\", \\"item2\\"]}"}',
                },
            ),
            ReadableSpan(
                name="process",
                start_time=1,
                end_time=2,
                attributes={
                    "tool.name": "process",
                    "output.value": '{"content": "{\\"processed\\": true}"}',
                },
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Process items"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallOutputEvaluator(  # type: ignore[call-arg]
            id="output-multiple",
            config={"name": "ToolCallOutputEvaluator", "strict": False},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_outputs": [
                    {"name": "fetch", "output": '{"data": ["item1", "item2"]}'},
                    {"name": "process", "output": '{"processed": true}'},
                ]
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_error_handling_validation(self) -> None:
        """Test error handling validation example."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallOutputEvaluator

        mock_spans = [
            ReadableSpan(
                name="validate_input",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "validate_input",
                    "output.value": '{"content": "{\\"valid\\": false, \\"error\\": \\"Invalid email format\\"}"}',
                },
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"email": "invalid-email"},
            agent_output={"status": "validation_failed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallOutputEvaluator(  # type: ignore[call-arg]
            id="error-validation",
            config={"name": "ToolCallOutputEvaluator", "strict": False},
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_outputs": [
                    {
                        "name": "validate_input",
                        "output": '{"valid": false, "error": "Invalid email format"}',
                    }
                ]
            },
        )

        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_non_strict_proportional_scoring(self) -> None:
        """Test non-strict mode with proportional scoring (2/3 outputs match)."""
        from opentelemetry.sdk.trace import ReadableSpan

        from uipath.eval.evaluators import ToolCallOutputEvaluator
        from uipath.eval.models import AgentExecution

        # Agent produced 3 outputs, but only 2 match expected
        mock_spans = [
            ReadableSpan(
                name="fetch_data",
                start_time=0,
                end_time=1,
                attributes={
                    "tool.name": "fetch_data",
                    "output.value": '{"content": "{\\"records\\": 150, \\"status\\": \\"success\\"}"}',  # ✓ Matches
                },
            ),
            ReadableSpan(
                name="process_data",
                start_time=1,
                end_time=2,
                attributes={
                    "tool.name": "process_data",
                    "output.value": '{"content": "{\\"processed\\": 100, \\"errors\\": 5}"}',  # ✗ Wrong values
                },
            ),
            ReadableSpan(
                name="save_results",
                start_time=2,
                end_time=3,
                attributes={
                    "tool.name": "save_results",
                    "output.value": '{"content": "{\\"saved\\": 150, \\"location\\": \\"/data/results.csv\\"}"}',  # ✓ Matches
                },
            ),
        ]

        agent_execution = AgentExecution(
            agent_input={"task": "Process data pipeline"},
            agent_output={"status": "completed"},
            agent_trace=mock_spans,
        )

        evaluator = ToolCallOutputEvaluator(  # type: ignore[call-arg]
            id="output-proportional",
            config={
                "name": "ToolCallOutputEvaluator",
                "strict": False,  # Proportional scoring
            },
        )

        result = await evaluator.validate_and_evaluate_criteria(
            agent_execution=agent_execution,
            evaluation_criteria={
                "tool_outputs": [
                    {
                        "name": "fetch_data",
                        "output": '{"records": 150, "status": "success"}',  # ✓ Matches
                    },
                    {
                        "name": "process_data",
                        "output": '{"processed": 150, "errors": 0}',  # ✗ Actual had errors: 5
                    },
                    {
                        "name": "save_results",
                        "output": '{"saved": 150, "location": "/data/results.csv"}',  # ✓ Matches
                    },
                ]
            },
        )

        # Score is 2/3 = 0.66 (2 out of 3 outputs matched)
        assert abs(result.score - 0.66) < 0.01  # Allow small floating point differences
