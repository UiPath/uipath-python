"""Tests for LegacyContextPrecisionEvaluator.

Tests span extraction, chunk normalization, and LLM evaluation.
"""

import json
from types import MappingProxyType
from unittest.mock import AsyncMock, patch

import pytest

from uipath._cli._evals._models._evaluator_base_params import EvaluatorBaseParams
from uipath.eval.evaluators import LegacyContextPrecisionEvaluator
from uipath.eval.evaluators.legacy_base_evaluator import LegacyEvaluationCriteria
from uipath.eval.models.models import (
    AgentExecution,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)


def _make_base_params() -> EvaluatorBaseParams:
    """Create base parameters for context precision evaluator."""
    return EvaluatorBaseParams(
        id="context-precision",
        category=LegacyEvaluatorCategory.LlmAsAJudge,
        evaluator_type=LegacyEvaluatorType.ContextPrecision,
        name="Context Precision",
        description="Evaluates context chunk relevance",
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-01T00:00:00Z",
        target_output_key="*",
    )


@pytest.fixture(autouse=True)
def mock_uipath_platform():
    """Fixture to mock UiPath platform for all tests."""
    with patch("uipath.platform.UiPath") as mock_uipath_class:
        mock_uipath_instance = mock_uipath_class.return_value
        mock_uipath_instance.llm = AsyncMock()
        yield mock_uipath_class


@pytest.fixture
def evaluator_with_mocked_llm():
    """Fixture to create evaluator with mocked LLM service."""
    evaluator = LegacyContextPrecisionEvaluator(
        **_make_base_params().model_dump(),
        config={},
        model="gpt-4.1-2025-04-14",
    )
    return evaluator


def _make_mock_span(input_query: str, output_chunks: list[str]):
    """Create a mock span with context grounding data."""

    class MockSpan:
        def __init__(self):
            self.attributes = MappingProxyType(
                {
                    "openinference.span.kind": "RETRIEVER",
                    "input.mime_type": "text/plain",
                    "input.value": input_query,
                    "output.value": json.dumps(
                        {
                            "documents": [
                                {"id": str(i), "text": chunk}
                                for i, chunk in enumerate(output_chunks)
                            ]
                        }
                    ),
                    "output.mime_type": "application/json",
                }
            )

    return MockSpan()


class TestLegacyContextPrecisionEvaluator:
    """Test suite for LegacyContextPrecisionEvaluator."""

    @pytest.mark.asyncio
    async def test_span_extraction_with_valid_data(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test extraction of context groundings from spans."""
        evaluator = evaluator_with_mocked_llm

        # Create mock span with context grounding data
        span = _make_mock_span(
            input_query="construction industry",
            output_chunks=["Building materials", "Safety codes", "Project management"],
        )

        # Extract context groundings
        groundings = evaluator._extract_context_groundings([span])

        assert len(groundings) == 1
        assert groundings[0]["query"] == "construction industry"
        assert len(groundings[0]["chunks"]) == 3
        # Chunks are JSON-serialized because they come from the output
        assert any("Building materials" in chunk for chunk in groundings[0]["chunks"])

    @pytest.mark.asyncio
    async def test_span_extraction_skips_invalid_spans(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test that spans without proper structure are skipped."""
        evaluator = evaluator_with_mocked_llm

        # Create spans: one valid, one invalid
        valid_span = _make_mock_span(
            input_query="test query",
            output_chunks=["chunk1"],
        )

        class InvalidSpan:
            attributes = MappingProxyType(
                {
                    "openinference.span.kind": "RETRIEVER",
                    # Missing input.value and output.value
                }
            )

        groundings = evaluator._extract_context_groundings([valid_span, InvalidSpan()])

        assert len(groundings) == 1
        assert groundings[0]["query"] == "test query"

    @pytest.mark.asyncio
    async def test_chunk_normalization(self, evaluator_with_mocked_llm) -> None:
        """Test normalization of various chunk formats."""
        evaluator = evaluator_with_mocked_llm

        # Test list of strings
        chunks = evaluator._normalize_chunks(["chunk1", "chunk2"])
        assert len(chunks) == 2
        assert all(isinstance(c, str) for c in chunks)

        # Test list of dicts
        chunks = evaluator._normalize_chunks(
            [
                {"id": "1", "text": "content1"},
                {"id": "2", "text": "content2"},
            ]
        )
        assert len(chunks) == 2
        assert all(isinstance(c, str) for c in chunks)

        # Test single string
        chunks = evaluator._normalize_chunks("single chunk")
        assert len(chunks) == 1
        assert chunks[0] == "single chunk"

    @pytest.mark.asyncio
    async def test_evaluation_with_mocked_llm(self, evaluator_with_mocked_llm) -> None:
        """Test evaluation logic with mocked LLM."""
        evaluator = evaluator_with_mocked_llm

        # Create mock spans
        span = _make_mock_span(
            input_query="python programming",
            output_chunks=[
                "Python syntax guide",
                "Python libraries overview",
                "JavaScript fundamentals",
            ],
        )

        # Extract context groundings from the span
        groundings = evaluator._extract_context_groundings([span])
        assert len(groundings) == 1
        assert groundings[0]["query"] == "python programming"
        assert len(groundings[0]["chunks"]) == 3

        # Test the grounding evaluation with mocked LLM response
        mock_llm_response = {
            "relevancies": [
                {"relevancy_score": 95},
                {"relevancy_score": 75},
                {"relevancy_score": 45},
            ]
        }

        with patch.object(
            evaluator, "_get_structured_llm_response", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_llm_response

            # Evaluate the context grounding
            scores = await evaluator._evaluate_context_grounding(
                groundings[0]["query"], groundings[0]["chunks"]
            )

            assert scores == [95, 75, 45]
            assert abs(sum(scores) / len(scores) - 71.66666667) < 0.01

    @pytest.mark.asyncio
    async def test_evaluation_with_no_context_groundings(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test evaluation when no context groundings are found."""
        evaluator = evaluator_with_mocked_llm

        # Create empty agent execution (no spans)
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output="",
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output="",
                expected_agent_behavior="",
            ),
        )

        assert result.score == 0.0
        assert "no context grounding" in result.details.lower()

    @pytest.mark.asyncio
    async def test_evaluation_multiple_context_calls(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test evaluation logic with multiple context grounding calls."""
        evaluator = evaluator_with_mocked_llm

        # Create two mock spans
        span1 = _make_mock_span(
            input_query="query 1",
            output_chunks=["chunk1a", "chunk1b"],
        )
        span2 = _make_mock_span(
            input_query="query 2",
            output_chunks=["chunk2a", "chunk2b", "chunk2c"],
        )

        # Extract context groundings from the spans
        groundings = evaluator._extract_context_groundings([span1, span2])
        assert len(groundings) == 2
        assert groundings[0]["query"] == "query 1"
        assert groundings[1]["query"] == "query 2"

        # Mock the LLM responses
        mock_llm_response_1 = {
            "relevancies": [{"relevancy_score": 90}, {"relevancy_score": 80}]
        }
        mock_llm_response_2 = {
            "relevancies": [
                {"relevancy_score": 85},
                {"relevancy_score": 75},
                {"relevancy_score": 65},
            ]
        }

        with patch.object(
            evaluator, "_get_structured_llm_response", new_callable=AsyncMock
        ) as mock_llm:
            # Return different responses for each call
            mock_llm.side_effect = [mock_llm_response_1, mock_llm_response_2]

            # Evaluate both context groundings
            scores1 = await evaluator._evaluate_context_grounding(
                groundings[0]["query"], groundings[0]["chunks"]
            )
            scores2 = await evaluator._evaluate_context_grounding(
                groundings[1]["query"], groundings[1]["chunks"]
            )

            # Verify individual scores
            assert scores1 == [90, 80]
            assert scores2 == [85, 75, 65]

            # Verify means
            mean1 = sum(scores1) / len(scores1)  # 85
            mean2 = sum(scores2) / len(scores2)  # 75
            overall_mean = (mean1 + mean2) / 2  # 80
            assert overall_mean == 80.0

    @pytest.mark.asyncio
    async def test_span_extraction_handles_json_parse_errors(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test that spans with invalid JSON are skipped."""
        evaluator = evaluator_with_mocked_llm

        class BadJsonSpan:
            attributes = MappingProxyType(
                {
                    "openinference.span.kind": "RETRIEVER",
                    "input.value": "test query",
                    "output.value": "not valid json",
                }
            )

        # Should not raise, should skip the span
        groundings = evaluator._extract_context_groundings([BadJsonSpan()])
        assert len(groundings) == 0

    @pytest.mark.asyncio
    async def test_serialization_of_dict_chunks(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test that dict chunks are properly serialized."""
        evaluator = evaluator_with_mocked_llm

        chunks = evaluator._normalize_chunks(
            [
                {"title": "Document 1", "content": "Some content"},
                {"title": "Document 2", "content": "More content"},
            ]
        )

        assert len(chunks) == 2
        assert all(isinstance(c, str) for c in chunks)
        # Should be JSON serialized
        assert '"title"' in chunks[0] or '"content"' in chunks[0]
