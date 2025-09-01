"""Tests for ExactMatchEvaluator."""

from typing import Any

import pytest

from uipath.eval.evaluators.exact_match_evaluator import ExactMatchEvaluator
from uipath.eval.models import EvaluationResult, ScoreType


class TestExactMatchEvaluator:
    """Test cases for ExactMatchEvaluator class."""

    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        evaluator = ExactMatchEvaluator()

        assert evaluator.name == "ExactMatchEvaluator"
        assert evaluator.description is None
        assert evaluator.target_output_key == "*"

    def test_init_custom_parameters(self):
        """Test initialization with custom parameters."""
        name = "CustomExactMatchEvaluator"
        description = "Custom exact match evaluation"
        target_key = "result"

        evaluator = ExactMatchEvaluator(
            name=name, description=description, target_output_key=target_key
        )

        assert evaluator.name == name
        assert evaluator.description == description
        assert evaluator.target_output_key == target_key

    @pytest.mark.asyncio
    async def test_evaluate_identical_outputs(self):
        """Test evaluation with identical expected and actual outputs."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"result": "success", "value": 42}
        actual_output = {"result": "success", "value": 42}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is True
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_different_outputs(self):
        """Test evaluation with different expected and actual outputs."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"result": "success", "value": 42}
        actual_output = {"result": "failure", "value": 42}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is False
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_different_values(self):
        """Test evaluation with different values."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"result": "success", "value": 42}
        actual_output = {"result": "success", "value": 43}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is False
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_extra_keys_in_actual(self):
        """Test evaluation when actual output has extra keys."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"result": "success"}
        actual_output = {"result": "success", "extra": "field"}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is False
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_missing_keys_in_actual(self):
        """Test evaluation when actual output is missing keys."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"result": "success", "value": 42}
        actual_output = {"result": "success"}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is False
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_nested_objects_identical(self):
        """Test evaluation with identical nested objects."""
        evaluator = ExactMatchEvaluator()

        expected_output = {
            "user": {"name": "John", "age": 30},
            "settings": {"theme": "dark", "notifications": True},
        }
        actual_output = {
            "user": {"name": "John", "age": 30},
            "settings": {"theme": "dark", "notifications": True},
        }

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is True
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_nested_objects_different(self):
        """Test evaluation with different nested objects."""
        evaluator = ExactMatchEvaluator()

        expected_output = {
            "user": {"name": "John", "age": 30},
            "settings": {"theme": "dark", "notifications": True},
        }
        actual_output = {
            "user": {"name": "John", "age": 31},  # Different age
            "settings": {"theme": "dark", "notifications": True},
        }

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is False
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_arrays_identical(self):
        """Test evaluation with identical arrays."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"items": [1, 2, 3], "labels": ["a", "b", "c"]}
        actual_output = {"items": [1, 2, 3], "labels": ["a", "b", "c"]}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is True
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_arrays_different_order(self):
        """Test evaluation with arrays in different order."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"items": [1, 2, 3]}
        actual_output = {"items": [3, 2, 1]}  # Different order

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is False
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_arrays_different_length(self):
        """Test evaluation with arrays of different lengths."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"items": [1, 2, 3]}
        actual_output = {"items": [1, 2]}  # Missing element

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is False
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_boolean_values(self):
        """Test evaluation with boolean values."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"success": True, "enabled": False}
        actual_output = {"success": True, "enabled": False}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is True
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_boolean_values_different(self):
        """Test evaluation with different boolean values."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"success": True, "enabled": False}
        actual_output = {"success": True, "enabled": True}  # Different boolean

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is False
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_number_normalization(self):
        """Test evaluation with number normalization (int vs float)."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"value": 42}
        actual_output = {"value": 42.0}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is True  # Should match after normalization
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_string_values(self):
        """Test evaluation with string values."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"message": "Hello world", "status": "ok"}
        actual_output = {"message": "Hello world", "status": "ok"}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is True
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_string_values_different(self):
        """Test evaluation with different string values."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"message": "Hello world"}
        actual_output = {"message": "Hello world!"}  # Extra exclamation

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is False
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_null_values(self):
        """Test evaluation with null values."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"value": None, "optional": None}
        actual_output = {"value": None, "optional": None}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is True
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_empty_objects(self):
        """Test evaluation with empty objects."""
        evaluator = ExactMatchEvaluator()

        expected_output: dict[str, Any] = {}
        actual_output: dict[str, Any] = {}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is True
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_empty_arrays(self):
        """Test evaluation with empty arrays."""
        evaluator = ExactMatchEvaluator()

        expected_output: dict[str, Any] = {"items": [], "tags": []}
        actual_output: dict[str, Any] = {"items": [], "tags": []}

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is True
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_type_mismatch(self):
        """Test evaluation with type mismatches."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"value": 42}  # Number
        actual_output = {"value": "42"}  # String

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is False
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_complex_nested_structure(self):
        """Test evaluation with complex nested structures."""
        evaluator = ExactMatchEvaluator()

        expected_output = {
            "users": [
                {
                    "id": 1,
                    "profile": {"name": "Alice", "age": 30},
                    "permissions": ["read", "write"],
                },
                {
                    "id": 2,
                    "profile": {"name": "Bob", "age": 25},
                    "permissions": ["read"],
                },
            ],
            "metadata": {"total": 2, "active": True},
        }

        actual_output = {
            "users": [
                {
                    "id": 1,
                    "profile": {"name": "Alice", "age": 30},
                    "permissions": ["read", "write"],
                },
                {
                    "id": 2,
                    "profile": {"name": "Bob", "age": 25},
                    "permissions": ["read"],
                },
            ],
            "metadata": {"total": 2, "active": True},
        }

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is True
        assert result.score_type == ScoreType.BOOLEAN

    @pytest.mark.asyncio
    async def test_evaluate_exception_handling(self):
        """Test evaluation handles exceptions gracefully."""
        evaluator = ExactMatchEvaluator()

        expected_output = {"test": "data"}
        actual_output = {"test": "data"}

        # Mock the _canonical_json method to raise an exception
        def mock_canonical_json(data):
            raise ValueError("Test exception")

        evaluator._canonical_json = mock_canonical_json  # type: ignore[method-assign]

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score is False
        assert (
            result.details is not None
            and "Error during evaluation: Test exception" in result.details
        )
        assert result.score_type == ScoreType.ERROR
