"""Tests for uipath_eval evaluators."""

import uuid

import pytest

from uipath_eval.evaluators.contains_evaluator import (
    ContainsEvaluationCriteria,
    ContainsEvaluator,
    ContainsEvaluatorConfig,
)
from uipath_eval.evaluators.exact_match_evaluator import (
    ExactMatchEvaluator,
    ExactMatchEvaluatorConfig,
)
from uipath_eval.evaluators.json_similarity_evaluator import (
    JsonSimilarityEvaluator,
    JsonSimilarityEvaluatorConfig,
)
from uipath_eval.evaluators.output_evaluator import OutputEvaluationCriteria
from uipath_eval.models.models import AgentExecution


def _id():
    return str(uuid.uuid4())


def _make_execution(output, agent_input=None):
    return AgentExecution(
        agent_input=agent_input or {},
        agent_output=output,
        agent_trace=[],
    )


class TestExactMatchEvaluator:
    def _make(self, case_sensitive=False, negated=False):
        return ExactMatchEvaluator(
            id=_id(),
            evaluatorConfig=ExactMatchEvaluatorConfig(
                case_sensitive=case_sensitive,
                negated=negated,
            ),
        )

    def _criteria(self, expected):
        return OutputEvaluationCriteria(expected_output=expected)

    @pytest.mark.asyncio
    async def test_exact_dict_match(self):
        result = await self._make().evaluate(
            _make_execution({"key": "value"}), self._criteria({"key": "value"})
        )
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_dict_mismatch(self):
        result = await self._make().evaluate(
            _make_execution({"key": "wrong"}), self._criteria({"key": "value"})
        )
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_string_case_insensitive(self):
        result = await self._make(case_sensitive=False).evaluate(
            _make_execution("Hello World"), self._criteria("hello world")
        )
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_string_case_sensitive_mismatch(self):
        result = await self._make(case_sensitive=True).evaluate(
            _make_execution("Hello World"), self._criteria("hello world")
        )
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_negated_match_returns_zero(self):
        result = await self._make(negated=True).evaluate(
            _make_execution("same"), self._criteria("same")
        )
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_negated_mismatch_returns_one(self):
        result = await self._make(negated=True).evaluate(
            _make_execution("different"), self._criteria("same")
        )
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_numeric_normalization(self):
        result = await self._make().evaluate(
            _make_execution({"score": 1}), self._criteria({"score": 1.0})
        )
        assert result.score == 1.0


class TestContainsEvaluator:
    def _make(self, case_sensitive=False, negated=False):
        return ContainsEvaluator(
            id=_id(),
            evaluatorConfig=ContainsEvaluatorConfig(
                case_sensitive=case_sensitive,
                negated=negated,
            ),
        )

    def _criteria(self, text):
        return ContainsEvaluationCriteria(search_text=text)

    @pytest.mark.asyncio
    async def test_contains_substring(self):
        result = await self._make().evaluate(
            _make_execution("The quick brown fox"), self._criteria("brown")
        )
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_does_not_contain(self):
        result = await self._make().evaluate(
            _make_execution("The quick brown fox"), self._criteria("cat")
        )
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_case_insensitive_match(self):
        result = await self._make(case_sensitive=False).evaluate(
            _make_execution("Hello World"), self._criteria("hello")
        )
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_case_sensitive_no_match(self):
        result = await self._make(case_sensitive=True).evaluate(
            _make_execution("Hello World"), self._criteria("hello")
        )
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_negated_contains_returns_zero(self):
        result = await self._make(negated=True).evaluate(
            _make_execution("The quick brown fox"), self._criteria("brown")
        )
        assert result.score == 0.0

    @pytest.mark.asyncio
    async def test_negated_missing_returns_one(self):
        result = await self._make(negated=True).evaluate(
            _make_execution("The quick brown fox"), self._criteria("cat")
        )
        assert result.score == 1.0


class TestJsonSimilarityEvaluator:
    def _make(self):
        return JsonSimilarityEvaluator(
            id=_id(),
            evaluatorConfig=JsonSimilarityEvaluatorConfig(),
        )

    def _criteria(self, expected):
        return OutputEvaluationCriteria(expected_output=expected)

    @pytest.mark.asyncio
    async def test_identical_dicts_score_one(self):
        result = await self._make().evaluate(
            _make_execution({"a": 1, "b": "hello"}),
            self._criteria({"a": 1, "b": "hello"}),
        )
        assert result.score == pytest.approx(1.0, abs=1e-6)

    @pytest.mark.asyncio
    async def test_completely_different_score_zero(self):
        result = await self._make().evaluate(
            _make_execution({"x": "foo"}), self._criteria({"a": "bar"})
        )
        assert result.score == pytest.approx(0.0, abs=1e-6)

    @pytest.mark.asyncio
    async def test_partial_match_between_zero_and_one(self):
        result = await self._make().evaluate(
            _make_execution({"a": 1, "b": "wrong"}),
            self._criteria({"a": 1, "b": "right"}),
        )
        assert 0.0 < result.score < 1.0

    @pytest.mark.asyncio
    async def test_numeric_tolerance(self):
        result = await self._make().evaluate(
            _make_execution({"v": 10.0}), self._criteria({"v": 10})
        )
        assert result.score == pytest.approx(1.0, abs=1e-6)

    @pytest.mark.asyncio
    async def test_empty_expected_score_one(self):
        result = await self._make().evaluate(_make_execution({}), self._criteria({}))
        assert result.score == pytest.approx(1.0, abs=1e-6)

    @pytest.mark.asyncio
    async def test_score_clamped(self):
        result = await self._make().evaluate(
            _make_execution({"a": "completely different text"}),
            self._criteria({"a": "xyz"}),
        )
        assert 0.0 <= result.score <= 1.0
