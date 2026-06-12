"""Tests for evaluation-level expectedOutput schema enhancement.

Tests the new optional `expectedOutput` field on EvaluationItem and the
runtime criteria resolution logic that injects it into output-based evaluators.
"""

import uuid
from typing import Any

import pytest
from pytest_mock.plugin import MockerFixture

from uipath.eval.evaluators.contains_evaluator import (
    ContainsEvaluationCriteria,
    ContainsEvaluator,
)
from uipath.eval.evaluators.exact_match_evaluator import ExactMatchEvaluator
from uipath.eval.evaluators.json_similarity_evaluator import (
    JsonSimilarityEvaluator,
)
from uipath.eval.evaluators.llm_as_judge_evaluator import LLMJudgeJustification
from uipath.eval.evaluators.llm_judge_output_evaluator import (
    LLMJudgeOutputEvaluator,
)
from uipath.eval.evaluators.output_evaluator import OutputEvaluationCriteria
from uipath.eval.models import NumericEvaluationResult
from uipath.eval.models.evaluation_set import (
    EvaluationItem,
    EvaluationSet,
)
from uipath.eval.models.models import AgentExecution

# ─────────────────────────────────────────────────────────────────
# Model Tests
# ─────────────────────────────────────────────────────────────────


class TestEvaluationItemExpectedOutput:
    """Test the new expectedOutput field on EvaluationItem."""

    def test_evaluation_item_with_dict_expected_output(self) -> None:
        """EvaluationItem with dict expectedOutput parses correctly."""
        item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Test Evaluation",
                "inputs": {"query": "2+2"},
                "expectedOutput": {"result": 4},
                "evaluationCriterias": {
                    "exact-match": None,
                },
            }
        )
        assert item.expected_output == {"result": 4}

    def test_evaluation_item_with_string_expected_output(self) -> None:
        """EvaluationItem with string expectedOutput parses correctly."""
        item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Test Evaluation",
                "inputs": {"query": "hello"},
                "expectedOutput": "Hello World",
                "evaluationCriterias": {
                    "exact-match": None,
                },
            }
        )
        assert item.expected_output == "Hello World"

    def test_evaluation_item_without_expected_output(self) -> None:
        """EvaluationItem without expectedOutput still works (backward compat)."""
        item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Test Evaluation",
                "inputs": {"query": "2+2"},
                "evaluationCriterias": {
                    "exact-match": {"expectedOutput": {"result": 4}},
                },
            }
        )
        assert item.expected_output is None

    def test_evaluation_item_with_null_expected_output(self) -> None:
        """EvaluationItem with explicit null expectedOutput parses as None."""
        item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Test Evaluation",
                "inputs": {"query": "2+2"},
                "expectedOutput": None,
                "evaluationCriterias": {
                    "exact-match": {"expectedOutput": {"result": 4}},
                },
            }
        )
        assert item.expected_output is None

    def test_evaluation_item_serialization_roundtrip_with_expected_output(
        self,
    ) -> None:
        """Serialization roundtrip preserves expectedOutput."""
        original_data = {
            "id": "eval-1",
            "name": "Test Evaluation",
            "inputs": {"query": "2+2"},
            "expectedOutput": {"result": 4},
            "evaluationCriterias": {
                "exact-match": None,
            },
        }
        item = EvaluationItem.model_validate(original_data)
        serialized = item.model_dump(by_alias=True, exclude_none=True)

        assert serialized["expectedOutput"] == {"result": 4}

        # Roundtrip
        item2 = EvaluationItem.model_validate(serialized)
        assert item2.expected_output == {"result": 4}

    def test_evaluation_item_serialization_omits_none_expected_output(self) -> None:
        """Serialization omits expectedOutput when None and exclude_none=True."""
        item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Test Evaluation",
                "inputs": {"query": "2+2"},
                "evaluationCriterias": {"exact-match": None},
            }
        )
        serialized = item.model_dump(by_alias=True, exclude_none=True)
        assert "expectedOutput" not in serialized

    def test_evaluation_set_with_evaluation_level_expected_output(self) -> None:
        """EvaluationSet with evaluation-level expectedOutput parses correctly."""
        evaluation_set = EvaluationSet.model_validate(
            {
                "id": "set-1",
                "name": "Test Set",
                "version": "1.0",
                "evaluatorConfigs": ["exact-match"],
                "evaluations": [
                    {
                        "id": "eval-1",
                        "name": "Test Evaluation",
                        "inputs": {"query": "2+2"},
                        "expectedOutput": {"result": 4},
                        "evaluationCriterias": {
                            "exact-match": None,
                        },
                    }
                ],
            }
        )
        assert evaluation_set.evaluations[0].expected_output == {"result": 4}

    def test_evaluation_item_with_python_field_name(self) -> None:
        """EvaluationItem works with Python field name (populate_by_name=True)."""
        item = EvaluationItem(
            id="eval-1",
            name="Test Evaluation",
            inputs={"query": "2+2"},
            expected_output={"result": 4},
            evaluation_criterias={"exact-match": None},
        )
        assert item.expected_output == {"result": 4}


# ─────────────────────────────────────────────────────────────────
# Runtime Criteria Resolution Tests
# ─────────────────────────────────────────────────────────────────


class TestRuntimeCriteriaResolution:
    """Test the runtime criteria merge logic for evaluation-level expectedOutput.

    These tests verify the merge logic directly against evaluators,
    simulating what runtime.py does when building typed criteria.
    """

    def _build_criteria(
        self,
        evaluator: Any,
        evaluation_item: EvaluationItem,
        evaluator_id: str,
    ) -> Any:
        """Simulate the runtime's criteria resolution logic.

        This mirrors the logic in runtime.py _execute_eval().
        """
        if evaluator_id not in evaluation_item.evaluation_criterias:
            return None

        evaluation_criteria = evaluation_item.evaluation_criterias[evaluator_id]

        # Inject evaluation-level expectedOutput for output-based evaluators
        if evaluation_item.expected_output is not None and issubclass(
            evaluator.evaluation_criteria_type,
            OutputEvaluationCriteria,
        ):
            if evaluation_criteria is None:
                evaluation_criteria = {
                    "expectedOutput": evaluation_item.expected_output
                }
            elif "expectedOutput" not in evaluation_criteria:
                evaluation_criteria = {
                    **evaluation_criteria,
                    "expectedOutput": evaluation_item.expected_output,
                }
            # else: per-evaluator expectedOutput takes precedence

        if evaluation_criteria:
            return evaluator.evaluation_criteria_type(**evaluation_criteria)
        return None

    @pytest.mark.asyncio
    async def test_evaluation_level_used_when_criteria_is_null(self) -> None:
        """When per-evaluator criteria is null, evaluation-level expectedOutput is injected."""
        evaluator_id = str(uuid.uuid4())
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": {"name": "Test"}, "id": evaluator_id}
        )
        evaluation_item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Test",
                "inputs": {"query": "2+2"},
                "expectedOutput": {"output": "Test output"},
                "evaluationCriterias": {evaluator_id: None},
            }
        )

        criteria = self._build_criteria(evaluator, evaluation_item, evaluator_id)

        assert criteria is not None
        assert isinstance(criteria, OutputEvaluationCriteria)
        assert criteria.expected_output == {"output": "Test output"}

    @pytest.mark.asyncio
    async def test_per_evaluator_overrides_evaluation_level(self) -> None:
        """Per-evaluator criteria expectedOutput overrides evaluation-level."""
        evaluator_id = str(uuid.uuid4())
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": {"name": "Test"}, "id": evaluator_id}
        )
        evaluation_item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Test",
                "inputs": {"query": "2+2"},
                "expectedOutput": {"result": "evaluation-level"},
                "evaluationCriterias": {
                    evaluator_id: {"expectedOutput": {"result": "per-evaluator"}}
                },
            }
        )

        criteria = self._build_criteria(evaluator, evaluation_item, evaluator_id)

        assert criteria is not None
        assert criteria.expected_output == {"result": "per-evaluator"}

    @pytest.mark.asyncio
    async def test_evaluation_level_injected_when_criteria_lacks_expected_output(
        self,
    ) -> None:
        """When criteria has other fields but no expectedOutput, evaluation-level is injected."""
        evaluator_id = str(uuid.uuid4())
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": {"name": "Test"}, "id": evaluator_id}
        )
        evaluation_item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Test",
                "inputs": {"query": "2+2"},
                "expectedOutput": {"result": 4},
                "evaluationCriterias": {evaluator_id: {"someOtherField": "value"}},
            }
        )

        criteria = self._build_criteria(evaluator, evaluation_item, evaluator_id)

        assert criteria is not None
        assert criteria.expected_output == {"result": 4}

    @pytest.mark.asyncio
    async def test_non_output_evaluator_unaffected_by_evaluation_level(self) -> None:
        """Non-output evaluators (ContainsEvaluator) ignore evaluation-level expectedOutput."""
        evaluator_id = str(uuid.uuid4())
        evaluator = ContainsEvaluator.model_validate(
            {"evaluatorConfig": {"name": "Test"}, "id": evaluator_id}
        )
        evaluation_item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Test",
                "inputs": {"query": "hello"},
                "expectedOutput": {"result": "should be ignored"},
                "evaluationCriterias": {evaluator_id: {"searchText": "hello"}},
            }
        )

        criteria = self._build_criteria(evaluator, evaluation_item, evaluator_id)

        assert criteria is not None
        assert isinstance(criteria, ContainsEvaluationCriteria)
        assert criteria.search_text == "hello"
        # expectedOutput was NOT injected
        assert not hasattr(criteria, "expected_output")

    @pytest.mark.asyncio
    async def test_no_evaluation_level_expected_output_no_injection(self) -> None:
        """When evaluation-level expectedOutput is None, no injection happens."""
        evaluator_id = str(uuid.uuid4())
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": {"name": "Test"}, "id": evaluator_id}
        )
        evaluation_item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Test",
                "inputs": {"query": "2+2"},
                "evaluationCriterias": {evaluator_id: None},
            }
        )

        criteria = self._build_criteria(evaluator, evaluation_item, evaluator_id)

        # No evaluation-level, no criteria -> None (will fall to default or error)
        assert criteria is None

    @pytest.mark.asyncio
    async def test_evaluation_level_string_expected_output(self) -> None:
        """String evaluation-level expectedOutput is injected correctly."""
        evaluator_id = str(uuid.uuid4())
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": {"name": "Test"}, "id": evaluator_id}
        )
        evaluation_item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Test",
                "inputs": {"query": "hello"},
                "expectedOutput": "Hello World",
                "evaluationCriterias": {evaluator_id: None},
            }
        )

        criteria = self._build_criteria(evaluator, evaluation_item, evaluator_id)

        assert criteria is not None
        assert criteria.expected_output == "Hello World"

    @pytest.mark.asyncio
    async def test_evaluation_level_empty_dict_expected_output(self) -> None:
        """Empty dict evaluation-level expectedOutput is still treated as present."""
        evaluator_id = str(uuid.uuid4())
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": {"name": "Test"}, "id": evaluator_id}
        )
        evaluation_item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Test",
                "inputs": {"query": "2+2"},
                "expectedOutput": {},
                "evaluationCriterias": {evaluator_id: None},
            }
        )

        criteria = self._build_criteria(evaluator, evaluation_item, evaluator_id)

        assert criteria is not None
        assert criteria.expected_output == {}


# ─────────────────────────────────────────────────────────────────
# Evaluator Integration Tests
# ─────────────────────────────────────────────────────────────────


class TestExactMatchWithEvaluationLevelExpectedOutput:
    """Test ExactMatchEvaluator with evaluation-level expectedOutput."""

    @pytest.mark.asyncio
    async def test_exact_match_with_evaluation_level_expected_output(self) -> None:
        """ExactMatchEvaluator uses evaluation-level expectedOutput when criteria is null."""
        execution = AgentExecution(
            agent_input={"query": "2+2"},
            agent_output={"result": 4},
            agent_trace=[],
        )
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": {"name": "Test"}, "id": str(uuid.uuid4())}
        )

        # Simulate runtime injection: evaluation-level expectedOutput -> criteria
        criteria = OutputEvaluationCriteria(
            expected_output={"result": 4}  # pyright: ignore[reportCallIssue]
        )
        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_exact_match_per_evaluator_overrides_evaluation_level(self) -> None:
        """Per-evaluator expectedOutput overrides evaluation-level."""
        execution = AgentExecution(
            agent_input={"query": "2+2"},
            agent_output={"result": 4},
            agent_trace=[],
        )
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": {"name": "Test"}, "id": str(uuid.uuid4())}
        )

        # Per-evaluator has different expectedOutput (mismatch)
        criteria = OutputEvaluationCriteria(
            expected_output={"result": 5}  # pyright: ignore[reportCallIssue]
        )
        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.0


class TestJsonSimilarityWithEvaluationLevelExpectedOutput:
    """Test JsonSimilarityEvaluator with evaluation-level expectedOutput."""

    @pytest.mark.asyncio
    async def test_json_similarity_with_evaluation_level_expected_output(self) -> None:
        """JsonSimilarityEvaluator uses evaluation-level expectedOutput."""
        execution = AgentExecution(
            agent_input={"input": "Test"},
            agent_output={"name": "John", "age": 30, "city": "NYC"},
            agent_trace=[],
        )
        evaluator = JsonSimilarityEvaluator.model_validate(
            {"evaluatorConfig": {"name": "Test"}, "id": str(uuid.uuid4())}
        )

        criteria = OutputEvaluationCriteria(
            expected_output={"name": "John", "age": 30, "city": "NYC"}  # pyright: ignore[reportCallIssue]
        )
        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0


class TestLLMJudgeWithEvaluationLevelExpectedOutput:
    """Test LLMJudgeOutputEvaluator with evaluation-level expectedOutput."""

    @pytest.mark.asyncio
    async def test_llm_judge_output_with_evaluation_level_expected_output(
        self, mocker: MockerFixture
    ) -> None:
        """LLMJudgeOutputEvaluator uses evaluation-level expectedOutput."""
        mock_tool_call = mocker.MagicMock()
        mock_tool_call.id = "call_1"
        mock_tool_call.name = "submit_evaluation"
        mock_tool_call.arguments = {
            "score": 90,
            "justification": "Output matches expected",
        }

        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(content=None, tool_calls=[mock_tool_call])
            )
        ]

        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        config = {
            "name": "LlmJudgeTest",
            "prompt": "Rate: {{ActualOutput}} vs {{ExpectedOutput}}",
            "model": "gpt-4o",
        }
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {
                "evaluatorConfig": config,
                "llm_service": mock_chat_completions,
                "id": str(uuid.uuid4()),
            }
        )

        execution = AgentExecution(
            agent_input={"query": "test"},
            agent_output={"result": "test output"},
            agent_trace=[],
        )

        # Criteria built from evaluation-level expectedOutput
        criteria = OutputEvaluationCriteria(
            expected_output={"result": "test output"}  # pyright: ignore[reportCallIssue]
        )
        result = await evaluator.evaluate(execution, criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 0.9
        assert isinstance(result.details, LLMJudgeJustification)


# ─────────────────────────────────────────────────────────────────
# Legacy Migration Compatibility Tests
# ─────────────────────────────────────────────────────────────────


class TestLegacyMigrationCompatibility:
    """Test that legacy migration path is unaffected by the new field."""

    def test_legacy_evaluation_set_still_migrates(self) -> None:
        """Legacy evaluation set without evaluation-level expectedOutput migrates correctly."""
        from uipath.eval.helpers import discriminate_eval_set

        legacy_data = {
            "id": "set-1",
            "fileName": "test.json",
            "name": "Legacy Set",
            "evaluatorRefs": ["exact-match"],
            "evaluations": [
                {
                    "id": "eval-1",
                    "name": "Test Evaluation",
                    "inputs": {"query": "2+2"},
                    "expectedOutput": {"result": 4},
                    "expectedAgentBehavior": "",
                    "evalSetId": "set-1",
                    "createdAt": "2024-01-01T00:00:00Z",
                    "updatedAt": "2024-01-01T00:00:00Z",
                }
            ],
            "batchSize": 10,
            "timeoutMinutes": 20,
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T00:00:00Z",
        }

        result = discriminate_eval_set(legacy_data)

        # Should parse as LegacyEvaluationSet (no version field)
        from uipath.eval.models.evaluation_set import LegacyEvaluationSet

        assert isinstance(result, LegacyEvaluationSet)

    def test_v1_evaluation_set_with_evaluation_level_expected_output(self) -> None:
        """v1.0 evaluation set with evaluation-level expectedOutput parses correctly."""
        from uipath.eval.helpers import discriminate_eval_set

        v1_data = {
            "id": "set-1",
            "name": "V1 Set",
            "version": "1.0",
            "evaluatorConfigs": ["exact-match"],
            "evaluations": [
                {
                    "id": "eval-1",
                    "name": "Test Evaluation",
                    "inputs": {"query": "2+2"},
                    "expectedOutput": {"result": 4},
                    "evaluationCriterias": {
                        "exact-match": None,
                    },
                }
            ],
        }

        result = discriminate_eval_set(v1_data)

        assert isinstance(result, EvaluationSet)
        assert result.evaluations[0].expected_output == {"result": 4}

    def test_v1_evaluation_set_without_evaluation_level_expected_output(self) -> None:
        """v1.0 evaluation set without evaluation-level expectedOutput still works."""
        from uipath.eval.helpers import discriminate_eval_set

        v1_data = {
            "id": "set-1",
            "name": "V1 Set",
            "version": "1.0",
            "evaluatorConfigs": ["exact-match"],
            "evaluations": [
                {
                    "id": "eval-1",
                    "name": "Test Evaluation",
                    "inputs": {"query": "2+2"},
                    "evaluationCriterias": {
                        "exact-match": {"expectedOutput": {"result": 4}},
                    },
                }
            ],
        }

        result = discriminate_eval_set(v1_data)

        assert isinstance(result, EvaluationSet)
        assert result.evaluations[0].expected_output is None


# ─────────────────────────────────────────────────────────────────
# End-to-End Criteria Resolution Tests
# ─────────────────────────────────────────────────────────────────


class TestEndToEndCriteriaResolution:
    """End-to-end tests that simulate the full runtime flow."""

    @pytest.mark.asyncio
    async def test_e2e_exact_match_null_criteria_with_evaluation_level(self) -> None:
        """Full flow: null criteria + evaluation-level -> ExactMatch evaluator gets expectedOutput."""
        evaluator_id = str(uuid.uuid4())
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": {"name": "Test"}, "id": evaluator_id}
        )
        evaluation_item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Calculator Test",
                "inputs": {"query": "2+2"},
                "expectedOutput": {"result": 4},
                "evaluationCriterias": {evaluator_id: None},
            }
        )
        execution = AgentExecution(
            agent_input={"query": "2+2"},
            agent_output={"result": 4},
            agent_trace=[],
        )

        # Simulate runtime merge
        evaluation_criteria = evaluation_item.evaluation_criterias[evaluator_id]
        if evaluation_item.expected_output is not None and issubclass(
            evaluator.evaluation_criteria_type, OutputEvaluationCriteria
        ):
            if evaluation_criteria is None:
                evaluation_criteria = {
                    "expectedOutput": evaluation_item.expected_output
                }
            elif "expectedOutput" not in evaluation_criteria:
                evaluation_criteria = {
                    **evaluation_criteria,
                    "expectedOutput": evaluation_item.expected_output,
                }

        assert evaluation_criteria is not None
        typed_criteria = evaluator.evaluation_criteria_type(**evaluation_criteria)
        result = await evaluator.evaluate(execution, typed_criteria)

        assert isinstance(result, NumericEvaluationResult)
        assert result.score == 1.0

    @pytest.mark.asyncio
    async def test_e2e_mixed_evaluators_with_evaluation_level(self) -> None:
        """Multiple evaluators: output-based gets evaluation-level, non-output ignores it."""
        exact_match_id = str(uuid.uuid4())
        contains_id = str(uuid.uuid4())

        exact_match_evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": {"name": "ExactMatch"}, "id": exact_match_id}
        )
        contains_evaluator = ContainsEvaluator.model_validate(
            {"evaluatorConfig": {"name": "Contains"}, "id": contains_id}
        )

        evaluation_item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Mixed Test",
                "inputs": {"query": "hello"},
                "expectedOutput": "Hello World",
                "evaluationCriterias": {
                    exact_match_id: None,  # Will get evaluation-level expectedOutput
                    contains_id: {"searchText": "Hello"},  # Unaffected
                },
            }
        )
        execution = AgentExecution(
            agent_input={"query": "hello"},
            agent_output="Hello World",
            agent_trace=[],
        )

        # Process exact-match (output-based)
        em_criteria = evaluation_item.evaluation_criterias[exact_match_id]
        if evaluation_item.expected_output is not None and issubclass(
            exact_match_evaluator.evaluation_criteria_type,
            OutputEvaluationCriteria,
        ):
            if em_criteria is None:
                em_criteria = {"expectedOutput": evaluation_item.expected_output}

        assert em_criteria is not None
        em_typed = exact_match_evaluator.evaluation_criteria_type(**em_criteria)
        em_result = await exact_match_evaluator.evaluate(execution, em_typed)
        assert em_result.score == 1.0

        # Process contains (non-output-based)
        c_criteria = evaluation_item.evaluation_criterias[contains_id]
        assert not issubclass(
            contains_evaluator.evaluation_criteria_type,
            OutputEvaluationCriteria,
        )
        assert c_criteria is not None
        c_typed = contains_evaluator.evaluation_criteria_type(**c_criteria)
        c_result = await contains_evaluator.evaluate(execution, c_typed)
        assert c_result.score == 1.0

    @pytest.mark.asyncio
    async def test_e2e_per_evaluator_override_with_evaluation_level(self) -> None:
        """Per-evaluator criteria overrides evaluation-level in full flow."""
        evaluator_id = str(uuid.uuid4())
        evaluator = ExactMatchEvaluator.model_validate(
            {"evaluatorConfig": {"name": "Test"}, "id": evaluator_id}
        )
        evaluation_item = EvaluationItem.model_validate(
            {
                "id": "eval-1",
                "name": "Override Test",
                "inputs": {"query": "2+2"},
                "expectedOutput": {"result": "wrong"},
                "evaluationCriterias": {
                    evaluator_id: {"expectedOutput": {"result": 4}}
                },
            }
        )
        execution = AgentExecution(
            agent_input={"query": "2+2"},
            agent_output={"result": 4},
            agent_trace=[],
        )

        # Simulate runtime merge
        evaluation_criteria = evaluation_item.evaluation_criterias[evaluator_id]
        if evaluation_item.expected_output is not None and issubclass(
            evaluator.evaluation_criteria_type, OutputEvaluationCriteria
        ):
            if evaluation_criteria is None:
                evaluation_criteria = {
                    "expectedOutput": evaluation_item.expected_output
                }
            elif "expectedOutput" not in evaluation_criteria:
                evaluation_criteria = {
                    **evaluation_criteria,
                    "expectedOutput": evaluation_item.expected_output,
                }
            # else: per-evaluator wins (this case)

        assert evaluation_criteria is not None
        typed_criteria = evaluator.evaluation_criteria_type(**evaluation_criteria)
        result = await evaluator.evaluate(execution, typed_criteria)

        # Per-evaluator says {"result": 4}, agent output is {"result": 4} -> match
        assert result.score == 1.0
        # Verify evaluation-level "wrong" was NOT used
        assert typed_criteria.expected_output == {"result": 4}
