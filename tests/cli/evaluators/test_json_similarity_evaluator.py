"""Tests for JsonSimilarityEvaluator.

Covers exact matches, numeric tolerance, string similarity, and nested structures.
"""

import json

import pytest

from uipath._cli._evals._models._evaluator_base_params import EvaluatorBaseParams
from uipath.eval.evaluators import LegacyJsonSimilarityEvaluator
from uipath.eval.evaluators.legacy_base_evaluator import LegacyEvaluationCriteria
from uipath.eval.models.models import (
    AgentExecution,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
)


def _make_base_params() -> EvaluatorBaseParams:
    return EvaluatorBaseParams(
        id="json-sim",
        category=LegacyEvaluatorCategory.Deterministic,
        evaluator_type=LegacyEvaluatorType.JsonSimilarity,
        name="JSON Similarity",
        description="Compares JSON structures",
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-01T00:00:00Z",
        target_output_key="*",
    )


class TestJsonSimilarityEvaluator:
    @pytest.mark.asyncio
    async def test_json_similarity_exact_score_1(self) -> None:
        evaluator = LegacyJsonSimilarityEvaluator(
            **_make_base_params().model_dump(),
            config={},
        )
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
            AgentExecution(
                agent_input={},
                agent_trace=[],
                agent_output=json.loads(actual_json),
            ),
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output=json.loads(expected_json),
                expected_agent_behavior="",
            ),
        )

        assert result.score == 68.0

    @pytest.mark.asyncio
    async def test_json_similarity_exact_score_2(self) -> None:
        evaluator = LegacyJsonSimilarityEvaluator(
            **_make_base_params().model_dump(),
            config={},
        )
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
            AgentExecution(
                agent_input={},
                agent_trace=[],
                agent_output=json.loads(actual_json),
            ),
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output=json.loads(expected_json),
                expected_agent_behavior="",
            ),
        )

        assert result.score >= 82.333
        assert result.score <= 82.3334

    @pytest.mark.asyncio
    async def test_json_similarity_exact_score_3(self) -> None:
        evaluator = LegacyJsonSimilarityEvaluator(
            **_make_base_params().model_dump(),
            config={},
        )
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
            AgentExecution(
                agent_input={},
                agent_trace=[],
                agent_output=json.loads(actual_json),
            ),
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output=json.loads(expected_json),
                expected_agent_behavior="",
            ),
        )

        assert result.score >= 33.333
        assert result.score <= 33.3334

    @pytest.mark.asyncio
    async def test_json_similarity_exact_score_4(self) -> None:
        evaluator = LegacyJsonSimilarityEvaluator(
            **_make_base_params().model_dump(),
            config={},
        )
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
            AgentExecution(
                agent_input={},
                agent_trace=[],
                agent_output=json.loads(actual_json),
            ),
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output=json.loads(expected_json),
                expected_agent_behavior="",
            ),
        )

        assert result.score == 43.24977043158861
