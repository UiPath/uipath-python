"""Tests for JsonSimilarityEvaluator.

Covers exact matches, numeric tolerance, string similarity, and nested structures.
"""

import json

import pytest

from uipath.eval.evaluators import JsonSimilarityEvaluator
from uipath.eval.models import EvaluationResult, ScoreType


class TestJsonSimilarityEvaluator:
    """Test cases for JsonSimilarityEvaluator class."""

    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        evaluator = JsonSimilarityEvaluator()

        assert evaluator.name == "JsonSimilarityEvaluator"
        assert evaluator.description is None
        assert evaluator.target_output_key == "*"

    def test_init_custom_parameters(self):
        """Test initialization with custom parameters."""
        name = "CustomJsonEvaluator"
        description = "Custom JSON comparison evaluator"
        target_key = "result"

        evaluator = JsonSimilarityEvaluator(
            name=name, description=description, target_output_key=target_key
        )

        assert evaluator.name == name
        assert evaluator.description == description
        assert evaluator.target_output_key == target_key

    @pytest.mark.asyncio
    async def test_evaluate_identical_outputs(self):
        """Test evaluation with identical expected and actual outputs."""
        evaluator = JsonSimilarityEvaluator()

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
        assert result.score == 100.0
        assert result.score_type == ScoreType.NUMERICAL

    @pytest.mark.asyncio
    async def test_evaluate_exception_handling(self):
        """Test evaluation handles exceptions gracefully."""
        evaluator = JsonSimilarityEvaluator()

        expected_output = {"test": "data"}
        actual_output = {"test": "data"}

        # Mock the _compare_json method to raise an exception
        def mock_compare_json(expected, actual):
            raise ValueError("Test exception")

        evaluator._compare_json = mock_compare_json  # type: ignore[method-assign]

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=expected_output,
            actual_output=actual_output,
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert isinstance(result, EvaluationResult)
        assert result.score == 0.0
        assert (
            result.details is not None
            and "Error during evaluation: Test exception" in result.details
        )
        assert result.score_type == ScoreType.ERROR

    @pytest.mark.asyncio
    async def test_json_similarity_exact_score_1(self) -> None:
        evaluator = JsonSimilarityEvaluator()
        expected_json = """
            {
                "user": {
                    "name": "Alice",
                    "age": 30,
                    "address": {
                        "city": "New York",
                        "zip": "10001"
                    }
                },
                "active": true
            }
            """

        actual_json = """
            {
                "user": {
                    "name": "Alicia",
                    "age": 28,
                    "address": {
                        "city": "New York",
                        "zip": "10002"
                    }
                },
                "active": false,
                "extraField": "Ignored"
            }
            """

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=json.loads(expected_json),
            actual_output=json.loads(actual_json),
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert result.score == 68.0

    @pytest.mark.asyncio
    async def test_json_similarity_exact_score_2(self) -> None:
        evaluator = JsonSimilarityEvaluator()
        expected_json = """
        {
            "users": [
                { "name": "Alice", "age": 25 },
                { "name": "Bob", "age": 30 }
            ]
        }
        """

        actual_json = """
        {
            "users": [
                { "name": "Alice", "age": 24 },
                { "name": "Robert", "age": 30 }
            ],
            "extraField": "Ignored"
        }
        """

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=json.loads(expected_json),
            actual_output=json.loads(actual_json),
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert result.score >= 82.333
        assert result.score <= 82.3334

    @pytest.mark.asyncio
    async def test_json_similarity_exact_score_3(self) -> None:
        evaluator = JsonSimilarityEvaluator()
        expected_json = """
        {
            "name": "Alice",
            "age": 30,
            "active": true
        }
        """

        actual_json = """
        {
            "name": "Alice",
            "age": "30",
            "active": "true"
        }
        """

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=json.loads(expected_json),
            actual_output=json.loads(actual_json),
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert result.score >= 33.333
        assert result.score <= 33.3334

    @pytest.mark.asyncio
    async def test_json_similarity_exact_score_4(self) -> None:
        evaluator = JsonSimilarityEvaluator()
        expected_json = """
        {
          "user": {
            "name": "Alice Johnson",
            "age": 30,
            "active": true,
            "address": {
              "street": "123 Main St",
              "city": "Metropolis",
              "zip": 90210
            }
          },
          "preferences": {
            "newsletter": true,
            "languages": ["en", "fr", "es"]
          },
          "metrics": {
            "visits": 100,
            "ratio": 0,
            "growth": 1.0
          },
          "posts": [
            { "title": "Hello World", "tags": ["intro", "welcome"] },
            { "title": "Deep Dive", "tags": ["advanced", "json", "parsing"] }
          ],
          "permissions": { "admin": false, "editor": true, "viewer": true },
          "notes": null,
          "bio": "Café au lait",
          "scores": [10, 9.5, "N/A", true],
          "settings": {
            "features": [
              { "key": "A", "enabled": true },
              { "key": "B", "enabled": false }
            ]
          }
        }
        """

        actual_json = """
        {
          "user": {
            "name": "Alice Johnson",
            "age": "30",
            "active": "true",
            "address": {
              "street": "123 Main St",
              "city": "Metropolis",
              "zip": "90210"
            }
          },
          "preferences": {
            "newsletter": "yes",
            "languages": ["en", "es", "fr", "de"]
          },
          "metrics": {
            "visits": 98,
            "ratio": 1e-11,
            "growth": 0.9
          },
          "posts": [
            { "title": "Hello-World", "tags": ["intro"] },
            { "title": "Deep  Dive", "tags": ["advanced", "json"] }
          ],
          "permissions": { "admin": "false", "editor": true },
          "bio": "Cafe au lait",
          "scores": [10, "9.5", "NA", "true"],
          "settings": {
            "features": [
              { "key": "B", "enabled": "false" },
              { "key": "A", "enabled": "true" }
            ]
          },
          "extra": { "debug": true }
        }
        """

        result = await evaluator.evaluate(
            agent_input=None,
            expected_output=json.loads(expected_json),
            actual_output=json.loads(actual_json),
            uipath_eval_spans=None,
            execution_logs="",
        )

        assert result.score == 43.24977043158861
