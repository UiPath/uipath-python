"""Tests for targetOutputKey path resolution in legacy evaluators.

Tests nested dot notation and array indexing in LegacyExactMatchEvaluator
and LegacyJsonSimilarityEvaluator.
"""

from typing import Any

import pytest

from uipath.eval.evaluators import (
    LegacyExactMatchEvaluator,
    LegacyJsonSimilarityEvaluator,
)
from uipath.eval.evaluators.base_legacy_evaluator import LegacyEvaluationCriteria
from uipath.eval.models.models import (
    AgentExecution,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)

NESTED_OUTPUT = {
    "order_id": "ORD-001",
    "customer": {
        "name": "John Doe",
        "email": "john.doe@example.com",
        "address": {
            "street": "123 Main St",
            "city": "Springfield",
            "zip_code": "62701",
        },
    },
    "items": [
        {"name": "Widget", "quantity": 2, "price": 9.99},
        {"name": "Gadget", "quantity": 1, "price": 24.99},
    ],
    "summary": {"total": 44.97, "item_count": 3, "status": "completed"},
    "tags": ["priority", "express", "verified"],
}


def _make_exact_match_params(target_output_key: str = "*") -> dict[str, Any]:
    return {
        "id": "test-exact",
        "category": LegacyEvaluatorCategory.Deterministic,
        "type": LegacyEvaluatorType.Equals,
        "name": "ExactMatch",
        "description": "Test",
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-01T00:00:00Z",
        "targetOutputKey": target_output_key,
    }


def _make_json_sim_params(target_output_key: str = "*") -> dict[str, Any]:
    return {
        "id": "test-json-sim",
        "category": LegacyEvaluatorCategory.Deterministic,
        "type": LegacyEvaluatorType.JsonSimilarity,
        "name": "JsonSimilarity",
        "description": "Test",
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-01T00:00:00Z",
        "targetOutputKey": target_output_key,
    }


class TestExactMatchWithNestedPaths:
    """Test LegacyExactMatchEvaluator with nested targetOutputKey paths."""

    @pytest.mark.asyncio
    async def test_nested_dot_path_summary_status(self) -> None:
        evaluator = LegacyExactMatchEvaluator(
            **_make_exact_match_params("summary.status")
        )
        result = await evaluator.evaluate(
            AgentExecution(agent_input={}, agent_trace=[], agent_output=NESTED_OUTPUT),
            LegacyEvaluationCriteria(
                expected_output=NESTED_OUTPUT, expected_agent_behavior=""
            ),
        )
        assert result.score is True

    @pytest.mark.asyncio
    async def test_nested_dot_path_customer_address_city(self) -> None:
        evaluator = LegacyExactMatchEvaluator(
            **_make_exact_match_params("customer.address.city")
        )
        result = await evaluator.evaluate(
            AgentExecution(agent_input={}, agent_trace=[], agent_output=NESTED_OUTPUT),
            LegacyEvaluationCriteria(
                expected_output=NESTED_OUTPUT, expected_agent_behavior=""
            ),
        )
        assert result.score is True

    @pytest.mark.asyncio
    async def test_array_index_items_0_name(self) -> None:
        evaluator = LegacyExactMatchEvaluator(
            **_make_exact_match_params("items[0].name")
        )
        result = await evaluator.evaluate(
            AgentExecution(agent_input={}, agent_trace=[], agent_output=NESTED_OUTPUT),
            LegacyEvaluationCriteria(
                expected_output=NESTED_OUTPUT, expected_agent_behavior=""
            ),
        )
        assert result.score is True

    @pytest.mark.asyncio
    async def test_array_index_tags_1(self) -> None:
        evaluator = LegacyExactMatchEvaluator(**_make_exact_match_params("tags[1]"))
        result = await evaluator.evaluate(
            AgentExecution(agent_input={}, agent_trace=[], agent_output=NESTED_OUTPUT),
            LegacyEvaluationCriteria(
                expected_output=NESTED_OUTPUT, expected_agent_behavior=""
            ),
        )
        assert result.score is True

    @pytest.mark.asyncio
    async def test_nested_path_mismatch_fails(self) -> None:
        evaluator = LegacyExactMatchEvaluator(
            **_make_exact_match_params("summary.status")
        )
        original_summary = NESTED_OUTPUT["summary"]
        assert isinstance(original_summary, dict)
        modified_summary = {**original_summary, "status": "pending"}
        different_output = {**NESTED_OUTPUT, "summary": modified_summary}
        result = await evaluator.evaluate(
            AgentExecution(
                agent_input={}, agent_trace=[], agent_output=different_output
            ),
            LegacyEvaluationCriteria(
                expected_output=NESTED_OUTPUT, expected_agent_behavior=""
            ),
        )
        assert result.score is False

    @pytest.mark.asyncio
    async def test_missing_path_in_both_passes(self) -> None:
        """When path doesn't exist in either output, both resolve to {} -> pass."""
        evaluator = LegacyExactMatchEvaluator(
            **_make_exact_match_params("nonexistent.path")
        )
        result = await evaluator.evaluate(
            AgentExecution(agent_input={}, agent_trace=[], agent_output=NESTED_OUTPUT),
            LegacyEvaluationCriteria(
                expected_output=NESTED_OUTPUT, expected_agent_behavior=""
            ),
        )
        assert result.score is True

    @pytest.mark.asyncio
    async def test_flat_key_backward_compatible(self) -> None:
        """Flat key like 'order_id' still works as before."""
        evaluator = LegacyExactMatchEvaluator(**_make_exact_match_params("order_id"))
        result = await evaluator.evaluate(
            AgentExecution(agent_input={}, agent_trace=[], agent_output=NESTED_OUTPUT),
            LegacyEvaluationCriteria(
                expected_output=NESTED_OUTPUT, expected_agent_behavior=""
            ),
        )
        assert result.score is True


class TestJsonSimilarityWithNestedPaths:
    """Test LegacyJsonSimilarityEvaluator with nested targetOutputKey paths."""

    @pytest.mark.asyncio
    async def test_json_similarity_with_target_key_summary(self) -> None:
        """JSON similarity on nested 'summary' object should score 100."""
        evaluator = LegacyJsonSimilarityEvaluator(**_make_json_sim_params("summary"))
        result = await evaluator.evaluate(
            AgentExecution(agent_input={}, agent_trace=[], agent_output=NESTED_OUTPUT),
            LegacyEvaluationCriteria(
                expected_output=NESTED_OUTPUT, expected_agent_behavior=""
            ),
        )
        assert result.score == 100.0

    @pytest.mark.asyncio
    async def test_json_similarity_with_target_key_customer(self) -> None:
        """JSON similarity on nested 'customer' object should score 100."""
        evaluator = LegacyJsonSimilarityEvaluator(**_make_json_sim_params("customer"))
        result = await evaluator.evaluate(
            AgentExecution(agent_input={}, agent_trace=[], agent_output=NESTED_OUTPUT),
            LegacyEvaluationCriteria(
                expected_output=NESTED_OUTPUT, expected_agent_behavior=""
            ),
        )
        assert result.score == 100.0

    @pytest.mark.asyncio
    async def test_json_similarity_with_target_key_items_0(self) -> None:
        """JSON similarity on items[0] should score 100 when matching."""
        evaluator = LegacyJsonSimilarityEvaluator(**_make_json_sim_params("items[0]"))
        result = await evaluator.evaluate(
            AgentExecution(agent_input={}, agent_trace=[], agent_output=NESTED_OUTPUT),
            LegacyEvaluationCriteria(
                expected_output=NESTED_OUTPUT, expected_agent_behavior=""
            ),
        )
        assert result.score == 100.0

    @pytest.mark.asyncio
    async def test_json_similarity_wildcard_unchanged(self) -> None:
        """Wildcard '*' should compare the full output (backward compatible)."""
        evaluator = LegacyJsonSimilarityEvaluator(**_make_json_sim_params("*"))
        result = await evaluator.evaluate(
            AgentExecution(agent_input={}, agent_trace=[], agent_output=NESTED_OUTPUT),
            LegacyEvaluationCriteria(
                expected_output=NESTED_OUTPUT, expected_agent_behavior=""
            ),
        )
        assert result.score == 100.0

    @pytest.mark.asyncio
    async def test_json_similarity_partial_match_with_target(self) -> None:
        """When target narrows to a sub-object, partial matches still work."""
        evaluator = LegacyJsonSimilarityEvaluator(**_make_json_sim_params("summary"))
        different_summary = {
            **NESTED_OUTPUT,
            "summary": {"total": 45.0, "item_count": 3, "status": "completed"},
        }
        result = await evaluator.evaluate(
            AgentExecution(
                agent_input={}, agent_trace=[], agent_output=different_summary
            ),
            LegacyEvaluationCriteria(
                expected_output=NESTED_OUTPUT, expected_agent_behavior=""
            ),
        )
        # total: 45.0 vs 44.97 -> very close but not exact
        assert result.score > 99.0
        assert result.score < 100.0
