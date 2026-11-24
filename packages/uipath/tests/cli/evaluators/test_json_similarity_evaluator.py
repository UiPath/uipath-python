"""Tests for JsonSimilarityEvaluator.

Covers exact matches, numeric tolerance, string similarity, and nested structures.
"""

import json
import random
import tracemalloc
from typing import Any

import pytest

from uipath.eval.evaluators import (
    JsonSimilarityEvaluator,
    LegacyJsonSimilarityEvaluator,
)
from uipath.eval.evaluators.base_legacy_evaluator import LegacyEvaluationCriteria
from uipath.eval.models.models import (
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
    WorkloadExecution,
)


def _make_base_params() -> dict[str, Any]:
    """Create base parameters for faithfulness evaluator."""
    return {
        "id": "json-sim",
        "category": LegacyEvaluatorCategory.Deterministic,
        "type": LegacyEvaluatorType.JsonSimilarity,
        "name": "JSON Similarity",
        "description": "Compares JSON structures",
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": "2025-01-01T00:00:00Z",
        "targetOutputKey": "*",
    }


class TestJsonSimilarityEvaluator:
    @pytest.mark.asyncio
    async def test_json_similarity_exact_score_1(self) -> None:
        evaluator = LegacyJsonSimilarityEvaluator(**_make_base_params())
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
            WorkloadExecution(
                agent_input={},
                workload_trace=[],
                workload_output=json.loads(actual_json),
            ),
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output=json.loads(expected_json),
                expected_agent_behavior="",
            ),
        )

        assert result.score == 68.0

    @pytest.mark.asyncio
    async def test_json_similarity_exact_score_2(self) -> None:
        evaluator = LegacyJsonSimilarityEvaluator(**_make_base_params())
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
            WorkloadExecution(
                agent_input={},
                workload_trace=[],
                workload_output=json.loads(actual_json),
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
        evaluator = LegacyJsonSimilarityEvaluator(**_make_base_params())
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
            WorkloadExecution(
                agent_input={},
                workload_trace=[],
                workload_output=json.loads(actual_json),
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
        evaluator = LegacyJsonSimilarityEvaluator(**_make_base_params())
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
            WorkloadExecution(
                agent_input={},
                workload_trace=[],
                workload_output=json.loads(actual_json),
            ),
            evaluation_criteria=LegacyEvaluationCriteria(
                expected_output=json.loads(expected_json),
                expected_agent_behavior="",
            ),
        )

        assert result.score == 43.24977043158861


def _reference_levenshtein(source: str, target: str) -> int:
    """Textbook full-matrix edit distance, used to check the optimized one."""
    rows = [[0] * (len(target) + 1) for _ in range(len(source) + 1)]
    for i in range(len(source) + 1):
        rows[i][0] = i
    for j in range(len(target) + 1):
        rows[0][j] = j
    for i in range(1, len(source) + 1):
        for j in range(1, len(target) + 1):
            rows[i][j] = min(
                rows[i - 1][j] + 1,
                rows[i][j - 1] + 1,
                rows[i - 1][j - 1] + (source[i - 1] != target[j - 1]),
            )
    return rows[-1][-1]


@pytest.fixture(params=[JsonSimilarityEvaluator, LegacyJsonSimilarityEvaluator])
def levenshtein(request: pytest.FixtureRequest) -> Any:
    """The edit-distance method of each JSON similarity evaluator."""
    evaluator_class = request.param
    return evaluator_class.__new__(evaluator_class)._levenshtein


class TestLevenshtein:
    @pytest.mark.parametrize(
        ("source", "target", "expected"),
        [
            ("", "", 0),
            ("", "abc", 3),
            ("abc", "", 3),
            ("same", "same", 0),
            ("kitten", "sitting", 3),
            ("flaw", "lawn", 2),
            ("prefix-a-suffix", "prefix-b-suffix", 1),
            ("abc", "abcabc", 3),
            ("aXa", "aa", 1),
        ],
    )
    def test_known_distances(
        self, levenshtein: Any, source: str, target: str, expected: int
    ) -> None:
        assert levenshtein(source, target) == expected
        assert levenshtein(target, source) == expected

    def test_matches_reference_on_random_strings(self, levenshtein: Any) -> None:
        rng = random.Random(7)
        for _ in range(300):
            source = "".join(rng.choices("abc", k=rng.randint(0, 12)))
            target = "".join(rng.choices("abc", k=rng.randint(0, 12)))
            assert levenshtein(source, target) == _reference_levenshtein(source, target)

    def test_long_identical_strings_do_no_matrix_work(self, levenshtein: Any) -> None:
        text = "lorem ipsum " * 170
        tracemalloc.start()
        try:
            assert levenshtein(text, text) == 0
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert peak < 1_000_000

    def test_memory_stays_linear_for_long_different_strings(
        self, levenshtein: Any
    ) -> None:
        source, target = "ab" * 750, "ba" * 750
        tracemalloc.start()
        try:
            distance = levenshtein(source, target)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert distance == 2
        # The full matrix for these 1500-char strings held about 18 MB.
        assert peak < 1_000_000
