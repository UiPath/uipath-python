"""Tests for LegacyExactMatchEvaluator.

Tests the exact match evaluation functionality including target_output_key support,
canonical JSON normalization, and number normalization.
"""

from unittest.mock import patch

import pytest

from uipath._cli._evals._models._evaluator_base_params import EvaluatorBaseParams
from uipath.eval.evaluators import LegacyExactMatchEvaluator
from uipath.eval.evaluators.legacy_base_evaluator import LegacyEvaluationCriteria
from uipath.eval.models.models import (
    AgentExecution,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)


def _make_base_params(target_output_key: str = "*") -> EvaluatorBaseParams:
    """Create base parameters for exact match evaluator."""
    return EvaluatorBaseParams(
        id="exact_match",
        category=LegacyEvaluatorCategory.Deterministic,
        evaluator_type=LegacyEvaluatorType.Equals,
        name="ExactMatch",
        description="Evaluates exact match of outputs",
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-01T00:00:00Z",
        target_output_key=target_output_key,
    )


@pytest.fixture
def evaluator():
    """Fixture to create evaluator."""
    with patch("uipath.platform.UiPath"):
        return LegacyExactMatchEvaluator(
            **_make_base_params().model_dump(),
            config={},
        )


@pytest.fixture
def evaluator_with_target_key():
    """Fixture to create evaluator with a specific target output key."""
    with patch("uipath.platform.UiPath"):
        return LegacyExactMatchEvaluator(
            **_make_base_params(target_output_key="result").model_dump(),
            config={},
        )


class TestLegacyExactMatchEvaluator:
    """Test suite for LegacyExactMatchEvaluator."""

    @pytest.mark.asyncio
    async def test_exact_match_same_strings(self, evaluator) -> None:
        """Test exact match with identical string outputs."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output="Hello World",
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output="Hello World",
                expected_agent_behavior="",
            ),
        )

        assert result.score is True
        assert isinstance(result.score, bool)

    @pytest.mark.asyncio
    async def test_exact_match_different_strings(self, evaluator) -> None:
        """Test exact match with different string outputs."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output="Hello World",
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output="Goodbye World",
                expected_agent_behavior="",
            ),
        )

        assert result.score is False

    @pytest.mark.asyncio
    async def test_exact_match_identical_dicts(self, evaluator) -> None:
        """Test exact match with identical dictionaries."""
        output = {"name": "John", "age": 30}
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=output,
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output=output,
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_different_dicts(self, evaluator) -> None:
        """Test exact match with different dictionaries."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"name": "John", "age": 30},
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"name": "Jane", "age": 25},
                expected_agent_behavior="",
            ),
        )

        assert result.score is False

    @pytest.mark.asyncio
    async def test_exact_match_dict_key_order_doesnt_matter(self, evaluator) -> None:
        """Test that canonical JSON normalization handles key order."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"a": 1, "b": 2},
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"b": 2, "a": 1},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_number_normalization_int_to_float(
        self, evaluator
    ) -> None:
        """Test that integers are normalized to floats for comparison."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"value": 42},
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"value": 42.0},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_number_normalization_in_list(self, evaluator) -> None:
        """Test number normalization in lists."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"values": [1, 2, 3]},
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"values": [1.0, 2.0, 3.0]},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_booleans_preserved(self, evaluator) -> None:
        """Test that booleans are not converted to numbers."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"active": True, "deleted": False},
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"active": True, "deleted": False},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_nested_structures(self, evaluator) -> None:
        """Test exact match with nested dictionaries and lists."""
        output = {
            "user": {
                "name": "John",
                "scores": [95, 87, 92],
                "active": True,
            },
            "metadata": {"version": 1.0},
        }

        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=output,
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output=output,
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_with_target_key_both_have_key(
        self, evaluator_with_target_key
    ) -> None:
        """Test target_output_key extraction when both outputs have the key."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"result": {"status": "success"}, "other": "ignore"},
        )

        result = await evaluator_with_target_key.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"result": {"status": "success"}, "other": "different"},
                expected_agent_behavior="",
            ),
        )

        # Both outputs have the target key, so both get extracted and compared
        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_with_target_key_missing_in_both(
        self, evaluator_with_target_key
    ) -> None:
        """Test target_output_key when key is missing in both outputs."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"other": "data"},
        )

        result = await evaluator_with_target_key.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"other": "different"},
                expected_agent_behavior="",
            ),
        )

        # When key is missing in both, both are set to {}, so they match
        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_with_target_key_missing_in_actual(
        self, evaluator_with_target_key
    ) -> None:
        """Test target_output_key when key is missing in actual output."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"other": "data"},
        )

        result = await evaluator_with_target_key.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"result": {"status": "success"}},
                expected_agent_behavior="",
            ),
        )

        # When key is missing in actual, both are set to {}, so they match
        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_with_target_key_missing_in_expected(
        self, evaluator_with_target_key
    ) -> None:
        """Test target_output_key when key is missing in expected output."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"result": {"status": "success"}},
        )

        result = await evaluator_with_target_key.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"other": "data"},
                expected_agent_behavior="",
            ),
        )

        # When key is missing in expected, both are set to {}, so they match
        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_with_wildcard_target_key(self, evaluator) -> None:
        """Test that wildcard target_output_key compares full outputs."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"data": "value", "extra": "field"},
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"data": "value", "extra": "field"},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_with_target_key_non_dict_inputs(
        self, evaluator_with_target_key
    ) -> None:
        """Test target_output_key with non-dict inputs (should compare as-is)."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output="string_value",
        )

        result = await evaluator_with_target_key.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output="other_string",
                expected_agent_behavior="",
            ),
        )

        assert result.score is False

    @pytest.mark.asyncio
    async def test_exact_match_null_values(self, evaluator) -> None:
        """Test exact match with None values."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"value": None},
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"value": None},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_empty_dict(self, evaluator) -> None:
        """Test exact match with empty dictionaries."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={},
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_empty_string(self, evaluator) -> None:
        """Test exact match with empty strings."""
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

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_unicode_characters(self, evaluator) -> None:
        """Test exact match with unicode characters."""
        output = {"greeting": "你好世界", "emoji": "🎉"}
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output=output,
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output=output,
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_whitespace_matters(self, evaluator) -> None:
        """Test that whitespace differences are detected."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output="Hello World",
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output="Hello  World",
                expected_agent_behavior="",
            ),
        )

        assert result.score is False

    @pytest.mark.asyncio
    async def test_exact_match_case_sensitivity(self, evaluator) -> None:
        """Test that string comparison is case sensitive."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output="Hello",
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output="hello",
                expected_agent_behavior="",
            ),
        )

        assert result.score is False

    @pytest.mark.asyncio
    async def test_exact_match_large_numbers(self, evaluator) -> None:
        """Test exact match with large numbers."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"value": 999999999999999},
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"value": 999999999999999.0},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_floating_point_precision(self, evaluator) -> None:
        """Test exact match with floating point numbers."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"pi": 3.14159},
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"pi": 3.14159},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_float_vs_int_zero(self, evaluator) -> None:
        """Test that 0 and 0.0 are considered equal."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"value": 0},
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"value": 0.0},
                expected_agent_behavior="",
            ),
        )

        assert result.score is True

    @pytest.mark.asyncio
    async def test_exact_match_with_target_key_different_values(
        self, evaluator_with_target_key
    ) -> None:
        """Test target_output_key with different values in target key."""
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={"result": {"status": "success"}, "other": "ignore"},
        )

        result = await evaluator_with_target_key.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={"result": {"status": "failed"}, "other": "ignore"},
                expected_agent_behavior="",
            ),
        )

        assert result.score is False

    @pytest.mark.asyncio
    async def test_canonical_json_normalization(self, evaluator) -> None:
        """Test that canonical JSON normalization works correctly."""
        # Create complex nested structure with mixed types
        agent_execution = AgentExecution(
            agent_input={},
            agent_trace=[],
            agent_output={
                "z_key": 1,
                "a_key": [3, 2, 1],
                "m_key": {"nested": 42},
            },
        )

        result = await evaluator.evaluate(
            agent_execution,
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output={
                    "a_key": [3, 2, 1],
                    "m_key": {"nested": 42.0},
                    "z_key": 1.0,
                },
                expected_agent_behavior="",
            ),
        )

        assert result.score is True
