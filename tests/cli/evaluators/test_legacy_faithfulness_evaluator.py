"""Tests for LegacyFaithfulnessEvaluator.

Tests span extraction, claim extraction (3-stage pipeline), and claim evaluation.
"""

import json
from types import MappingProxyType
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from uipath._cli._evals._models._evaluator_base_params import EvaluatorBaseParams
from uipath.eval.evaluators import LegacyFaithfulnessEvaluator
from uipath.eval.evaluators.legacy_base_evaluator import LegacyEvaluationCriteria
from uipath.eval.models.models import (
    AgentExecution,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)


def _make_base_params() -> EvaluatorBaseParams:
    """Create base parameters for faithfulness evaluator."""
    return EvaluatorBaseParams(
        id="faithfulness",
        category=LegacyEvaluatorCategory.LlmAsAJudge,
        evaluator_type=LegacyEvaluatorType.Faithfulness,
        name="Faithfulness",
        description="Evaluates faithfulness of claims against context",
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-01T00:00:00Z",
        target_output_key="*",
    )


@pytest.fixture
def evaluator_with_mocked_llm():
    """Fixture to create evaluator with mocked LLM service."""
    with patch("uipath.platform.UiPath"):
        evaluator = LegacyFaithfulnessEvaluator(
            **_make_base_params().model_dump(),
            config={},
            model="gpt-4.1-2025-04-14",
        )
    return evaluator


def _make_mock_span(tool_name: str, output_data: dict[str, Any]):
    """Create a mock span with tool call data."""

    class MockSpan:
        def __init__(self):
            self.attributes = MappingProxyType(
                {
                    "openinference.span.kind": tool_name,
                    "output.value": json.dumps(output_data),
                }
            )

    return MockSpan()


def _make_retriever_span(query: str, documents: list[str]):
    """Create a mock RETRIEVER span with context grounding data."""
    return _make_mock_span(
        "RETRIEVER",
        {"documents": [{"id": str(i), "text": doc} for i, doc in enumerate(documents)]},
    )


class TestLegacyFaithfulnessEvaluator:
    """Test suite for LegacyFaithfulnessEvaluator."""

    @pytest.mark.asyncio
    async def test_context_source_extraction_from_tool_calls(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test extraction of context sources from tool call spans."""
        evaluator = evaluator_with_mocked_llm

        # Create mock spans with tool outputs
        span1 = _make_mock_span("TOOL_CALL", {"result": "Tool output 1"})
        span2 = _make_mock_span("TOOL_CALL", {"result": "Tool output 2"})

        # Extract context sources
        sources = evaluator._extract_context_sources([span1, span2])

        assert len(sources) == 2
        assert all("content" in s and "source" in s for s in sources)

    @pytest.mark.asyncio
    async def test_context_source_extraction_from_retriever(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test extraction of context sources from RETRIEVER spans."""
        evaluator = evaluator_with_mocked_llm

        # Create mock RETRIEVER span with documents
        span = _make_retriever_span(
            "construction", ["Building materials info", "Safety codes"]
        )

        # Extract context sources (should extract each document individually)
        sources = evaluator._extract_context_sources([span])

        assert len(sources) == 2
        assert all(s["source"] == "Context Grounding" for s in sources)
        # Check that we have both documents
        contents = [s["content"] for s in sources]
        assert any("Building materials" in c for c in contents)
        assert any("Safety codes" in c for c in contents)

    @pytest.mark.asyncio
    async def test_context_source_extraction_skips_invalid_spans(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test that spans without proper structure are skipped."""
        evaluator = evaluator_with_mocked_llm

        class InvalidSpan:
            attributes = MappingProxyType(
                {
                    "openinference.span.kind": "TOOL_CALL",
                    # Missing output.value
                }
            )

        # Should skip invalid span
        sources = evaluator._extract_context_sources([InvalidSpan()])
        assert len(sources) == 0

    @pytest.mark.asyncio
    async def test_select_verifiable_sentences(self, evaluator_with_mocked_llm) -> None:
        """Test Stage 1: Selection of verifiable sentences."""
        evaluator = evaluator_with_mocked_llm

        agent_output = (
            "The capital of France is Paris. Do you agree? This is important."
        )

        mock_response = {"sentences": ["The capital of France is Paris."]}

        with patch.object(
            evaluator, "_get_structured_llm_response", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_response

            sentences = await evaluator._select_verifiable_sentences(agent_output)

            assert len(sentences) == 1
            assert "capital of France" in sentences[0]

    @pytest.mark.asyncio
    async def test_disambiguate_sentences(self, evaluator_with_mocked_llm) -> None:
        """Test Stage 2: Disambiguation of sentences."""
        evaluator = evaluator_with_mocked_llm

        verifiable_sentences = ["It is located in Western Europe."]
        full_output = "France is a country. It is located in Western Europe."

        mock_response = {
            "disambiguated": [
                {
                    "original": "It is located in Western Europe.",
                    "disambiguated": "France is located in Western Europe.",
                }
            ]
        }

        with patch.object(
            evaluator, "_get_structured_llm_response", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_response

            result = await evaluator._disambiguate_sentences(
                verifiable_sentences, full_output
            )

            assert len(result) == 1
            assert result[0]["disambiguated"] == "France is located in Western Europe."

    @pytest.mark.asyncio
    async def test_decompose_to_claims(self, evaluator_with_mocked_llm) -> None:
        """Test Stage 3: Decomposition into standalone claims."""
        evaluator = evaluator_with_mocked_llm

        disambiguated = [
            {
                "original": "Paris and Lyon have populations over 1 million.",
                "disambiguated": "Paris and Lyon have populations over 1 million.",
            }
        ]
        full_output = (
            "France has major cities. Paris and Lyon have populations over 1 million."
        )

        mock_response = {
            "claims": [
                {
                    "claim": "Paris has a population over 1 million",
                    "original_sentence": "1",
                },
                {
                    "claim": "Lyon has a population over 1 million",
                    "original_sentence": "1",
                },
            ]
        }

        with patch.object(
            evaluator, "_get_structured_llm_response", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_response

            claims = await evaluator._decompose_to_claims(disambiguated, full_output)

            assert len(claims) == 2
            assert any("Paris" in c["text"] for c in claims)
            assert any("Lyon" in c["text"] for c in claims)

    @pytest.mark.asyncio
    async def test_evaluate_claim_stance_supports(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test claim stance evaluation when source supports claim."""
        evaluator = evaluator_with_mocked_llm

        claim = "Paris is the capital of France"
        context = "The capital of France is Paris, a major European city."

        mock_response = {"stance": "SUPPORTS"}

        with patch.object(
            evaluator, "_get_structured_llm_response", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_response

            stance = await evaluator._evaluate_claim_stance(claim, context)

            assert stance == "SUPPORTS"

    @pytest.mark.asyncio
    async def test_evaluate_claim_stance_contradicts(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test claim stance evaluation when source contradicts claim."""
        evaluator = evaluator_with_mocked_llm

        claim = "Paris is in Germany"
        context = "Paris is a city in France, not Germany."

        mock_response = {"stance": "CONTRADICTS"}

        with patch.object(
            evaluator, "_get_structured_llm_response", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_response

            stance = await evaluator._evaluate_claim_stance(claim, context)

            assert stance == "CONTRADICTS"

    @pytest.mark.asyncio
    async def test_evaluate_claim_stance_irrelevant(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test claim stance evaluation when source is irrelevant."""
        evaluator = evaluator_with_mocked_llm

        claim = "Paris is the capital of France"
        context = "The Eiffel Tower is made of iron."

        mock_response = {"stance": "IRRELEVANT"}

        with patch.object(
            evaluator, "_get_structured_llm_response", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_response

            stance = await evaluator._evaluate_claim_stance(claim, context)

            assert stance == "IRRELEVANT"

    @pytest.mark.asyncio
    async def test_evaluate_claims_against_context(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test evaluation of claims against multiple context sources."""
        evaluator = evaluator_with_mocked_llm

        claims = [
            {"text": "Paris is in France", "original_sentence": "1"},
            {"text": "Tokyo is in Japan", "original_sentence": "2"},
        ]
        context_sources = [
            {"content": "Paris is the capital of France", "source": "Source 1"},
            {"content": "Tokyo is the capital of Japan", "source": "Source 2"},
        ]

        # Mock stance evaluations
        with patch.object(
            evaluator, "_evaluate_claim_stance", new_callable=AsyncMock
        ) as mock_stance:
            # Return SUPPORTS for both claims
            mock_stance.side_effect = ["SUPPORTS", "SUPPORTS", "SUPPORTS", "SUPPORTS"]

            evaluations = await evaluator._evaluate_claims_against_context(
                claims, context_sources
            )

            assert len(evaluations) == 2
            assert all(e["is_grounded"] for e in evaluations)
            assert len(evaluations[0]["supporting_sources"]) == 2
            assert len(evaluations[1]["supporting_sources"]) == 2

    @pytest.mark.asyncio
    async def test_claim_grounding_with_contradicting_source(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test that claims with contradicting sources are not grounded."""
        evaluator = evaluator_with_mocked_llm

        claims = [
            {"text": "The Earth is flat", "original_sentence": "1"},
        ]
        context_sources = [
            {"content": "The Earth is spherical", "source": "Science Source"},
        ]

        with patch.object(
            evaluator, "_evaluate_claim_stance", new_callable=AsyncMock
        ) as mock_stance:
            mock_stance.return_value = "CONTRADICTS"

            evaluations = await evaluator._evaluate_claims_against_context(
                claims, context_sources
            )

            assert len(evaluations) == 1
            assert not evaluations[0]["is_grounded"]
            assert len(evaluations[0]["contradicting_sources"]) == 1

    @pytest.mark.asyncio
    async def test_full_evaluation_with_no_agent_output(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test evaluation when no agent output is provided."""
        evaluator = evaluator_with_mocked_llm

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
        assert "no agent output" in result.details.lower()

    @pytest.mark.asyncio
    async def test_full_evaluation_with_no_context_sources(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test evaluation when no context sources are available."""
        evaluator = evaluator_with_mocked_llm

        # Create a span without output (no context source)
        class NoOutputSpan:
            attributes = MappingProxyType(
                {
                    "openinference.span.kind": "TOOL_CALL",
                    # No output.value
                }
            )

        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output="The sky is blue.",
        )

        with patch.object(evaluator, "_extract_context_sources", return_value=[]):
            result = await evaluator.evaluate(
                agent_execution,
                evaluation_criteria=LegacyEvaluationCriteria(
                    expected_output="The sky is blue.",
                    expected_agent_behavior="",
                ),
            )

            assert result.score == 0.0
            assert "no context sources" in result.details.lower()

    @pytest.mark.asyncio
    async def test_full_evaluation_with_no_verifiable_claims(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test evaluation when no verifiable claims are found."""
        evaluator = evaluator_with_mocked_llm

        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output="Just a greeting.",
        )

        with (
            patch.object(
                evaluator,
                "_extract_context_sources",
                return_value=[{"content": "Some context", "source": "Test"}],
            ),
            patch.object(
                evaluator, "_extract_claims", new_callable=AsyncMock
            ) as mock_claims,
        ):
            mock_claims.return_value = []

            result = await evaluator.evaluate(
                agent_execution,
                evaluation_criteria=LegacyEvaluationCriteria(
                    expected_output="Just a greeting.",
                    expected_agent_behavior="",
                ),
            )

            assert result.score == 100.0
            assert "no verifiable claims" in result.details.lower()

    @pytest.mark.asyncio
    async def test_full_evaluation_with_grounded_claims(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test full evaluation flow with grounded claims."""
        evaluator = evaluator_with_mocked_llm

        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output="Paris is in France.",
        )

        # Mock the extraction and evaluation steps
        with (
            patch.object(
                evaluator,
                "_extract_context_sources",
                return_value=[
                    {
                        "content": "Paris is the capital of France",
                        "source": "Context Grounding",
                    }
                ],
            ),
            patch.object(
                evaluator, "_extract_claims", new_callable=AsyncMock
            ) as mock_claims,
            patch.object(
                evaluator, "_evaluate_claims_against_context", new_callable=AsyncMock
            ) as mock_eval,
        ):
            mock_claims.return_value = [
                {"text": "Paris is in France", "original_sentence": "1"}
            ]
            mock_eval.return_value = [
                {
                    "claim": "Paris is in France",
                    "original_sentence": "1",
                    "is_grounded": True,
                    "supporting_sources": ["Context Grounding"],
                    "contradicting_sources": [],
                }
            ]

            result = await evaluator.evaluate(
                agent_execution,
                evaluation_criteria=LegacyEvaluationCriteria(
                    expected_output="Paris is in France.",
                    expected_agent_behavior="",
                ),
            )

            assert result.score == 100.0
            assert "GROUNDED CLAIMS" in result.details
            assert "Paris is in France" in result.details

    @pytest.mark.asyncio
    async def test_full_evaluation_with_mixed_claims(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test full evaluation with both grounded and ungrounded claims."""
        evaluator = evaluator_with_mocked_llm

        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output="Paris is in France. The sky is green.",
        )

        # Mock the extraction and evaluation steps
        with (
            patch.object(
                evaluator,
                "_extract_context_sources",
                return_value=[
                    {
                        "content": "Paris is the capital of France",
                        "source": "Context Grounding",
                    }
                ],
            ),
            patch.object(
                evaluator, "_extract_claims", new_callable=AsyncMock
            ) as mock_claims,
            patch.object(
                evaluator, "_evaluate_claims_against_context", new_callable=AsyncMock
            ) as mock_eval,
        ):
            mock_claims.return_value = [
                {"text": "Paris is in France", "original_sentence": "1"},
                {"text": "The sky is green", "original_sentence": "2"},
            ]
            mock_eval.return_value = [
                {
                    "claim": "Paris is in France",
                    "original_sentence": "1",
                    "is_grounded": True,
                    "supporting_sources": ["Context Grounding"],
                    "contradicting_sources": [],
                },
                {
                    "claim": "The sky is green",
                    "original_sentence": "2",
                    "is_grounded": False,
                    "supporting_sources": [],
                    "contradicting_sources": [],
                },
            ]

            result = await evaluator.evaluate(
                agent_execution,
                evaluation_criteria=LegacyEvaluationCriteria(
                    expected_output="Paris is in France. The sky is green.",
                    expected_agent_behavior="",
                ),
            )

            assert result.score == 50.0
            assert "1/2" in result.details
            assert "GROUNDED CLAIMS" in result.details
            assert "UNGROUNDED CLAIMS" in result.details

    @pytest.mark.asyncio
    async def test_serialize_content_handles_various_types(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test serialization of various content types."""
        evaluator = evaluator_with_mocked_llm

        # Test string
        result = evaluator._serialize_content("simple string")
        assert result == "simple string"

        # Test dict
        result = evaluator._serialize_content({"key": "value"})
        assert "key" in result and "value" in result

        # Test list
        result = evaluator._serialize_content(["item1", "item2"])
        assert "item1" in result and "item2" in result

    @pytest.mark.asyncio
    async def test_evaluate_claim_stance_with_invalid_response(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test that invalid stance responses default to IRRELEVANT."""
        evaluator = evaluator_with_mocked_llm

        claim = "Test claim"
        context = "Test context"

        mock_response = {"stance": "INVALID_STANCE"}

        with patch.object(
            evaluator, "_get_structured_llm_response", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = mock_response

            stance = await evaluator._evaluate_claim_stance(claim, context)

            assert stance == "IRRELEVANT"

    @pytest.mark.asyncio
    async def test_format_justification_structure(
        self, evaluator_with_mocked_llm
    ) -> None:
        """Test the structure of formatted justification."""
        evaluator = evaluator_with_mocked_llm

        claim_evaluations = [
            {
                "claim": "Grounded claim 1",
                "original_sentence": "1",
                "is_grounded": True,
                "supporting_sources": ["Source A", "Source B"],
                "contradicting_sources": [],
            },
            {
                "claim": "Ungrounded claim",
                "original_sentence": "2",
                "is_grounded": False,
                "supporting_sources": [],
                "contradicting_sources": ["Source C"],
            },
        ]

        justification = evaluator._format_justification(50.0, claim_evaluations)

        assert "Overall Faithfulness: 50.0/100" in justification
        assert "1/2" in justification
        assert "GROUNDED CLAIMS" in justification
        assert "UNGROUNDED CLAIMS" in justification
        assert "Grounded claim 1" in justification
        assert "Ungrounded claim" in justification
        assert "Source A" in justification
        assert "Source C" in justification
