"""Tests for evaluator schema functionality and base evaluator features.

This module tests:
- Config schema generation for all evaluators
- Evaluation criteria schema generation for all evaluators
- Base evaluator functionality (type extraction, validation)
- Generic type parameter handling
"""

import uuid

import pytest
from pydantic import ValidationError
from pytest_mock.plugin import MockerFixture

from uipath.eval.evaluators.exact_match_evaluator import (
    ExactMatchEvaluator,
    ExactMatchEvaluatorConfig,
)
from uipath.eval.evaluators.json_similarity_evaluator import (
    JsonSimilarityEvaluator,
    JsonSimilarityEvaluatorConfig,
)
from uipath.eval.evaluators.llm_as_judge_evaluator import (
    LLMJudgeMixin,
)
from uipath.eval.evaluators.llm_judge_output_evaluator import (
    LLMJudgeOutputEvaluator,
    LLMJudgeOutputEvaluatorConfig,
)
from uipath.eval.evaluators.llm_judge_trajectory_evaluator import (
    LLMJudgeTrajectoryEvaluator,
)
from uipath.eval.evaluators.output_evaluator import (
    OutputEvaluationCriteria,
)
from uipath.eval.evaluators.tool_call_args_evaluator import (
    ToolCallArgsEvaluationCriteria,
    ToolCallArgsEvaluator,
    ToolCallArgsEvaluatorConfig,
)
from uipath.eval.evaluators.tool_call_count_evaluator import (
    ToolCallCountEvaluationCriteria,
    ToolCallCountEvaluator,
    ToolCallCountEvaluatorConfig,
)
from uipath.eval.evaluators.tool_call_order_evaluator import (
    ToolCallOrderEvaluationCriteria,
    ToolCallOrderEvaluator,
    ToolCallOrderEvaluatorConfig,
)
from uipath.eval.evaluators.tool_call_output_evaluator import (
    ToolCallOutputEvaluationCriteria,
    ToolCallOutputEvaluator,
    ToolCallOutputEvaluatorConfig,
)


@pytest.fixture
def sample_config_data() -> dict[str, str | bool | int | float]:
    """Sample config data for testing."""
    return {
        "name": "TestEvaluator",
        "threshold": 0.8,
        "case_sensitive": False,
        "strict": True,
    }


class TestEvaluatorSchemas:
    """Test schema generation for all evaluators."""

    def test_exact_match_evaluator_schemas(self) -> None:
        """Test ExactMatchEvaluator schema generation."""
        # Test config schema
        config_schema = ExactMatchEvaluator.get_config_schema()
        assert isinstance(config_schema, dict)
        assert "properties" in config_schema
        assert "name" in config_schema["properties"]
        assert "case_sensitive" in config_schema["properties"]

        # Test criteria schema
        criteria_schema = ExactMatchEvaluator.get_evaluation_criteria_schema()
        assert isinstance(criteria_schema, dict)
        assert "properties" in criteria_schema
        assert "expected_output" in criteria_schema["properties"]

    def test_json_similarity_evaluator_schemas(self) -> None:
        """Test JsonSimilarityEvaluator schema generation."""
        # Test config schema
        config_schema = JsonSimilarityEvaluator.get_config_schema()
        assert isinstance(config_schema, dict)
        assert "properties" in config_schema
        assert "name" in config_schema["properties"]

        # Test criteria schema
        criteria_schema = JsonSimilarityEvaluator.get_evaluation_criteria_schema()
        assert isinstance(criteria_schema, dict)
        assert "properties" in criteria_schema
        assert "expected_output" in criteria_schema["properties"]

    def test_tool_call_order_evaluator_schemas(self) -> None:
        """Test ToolCallOrderEvaluator schema generation."""
        # Test config schema
        config_schema = ToolCallOrderEvaluator.get_config_schema()
        assert isinstance(config_schema, dict)
        assert "properties" in config_schema
        assert "name" in config_schema["properties"]
        assert "strict" in config_schema["properties"]

        # Test criteria schema
        criteria_schema = ToolCallOrderEvaluator.get_evaluation_criteria_schema()
        assert isinstance(criteria_schema, dict)
        assert "properties" in criteria_schema
        assert "tool_calls_order" in criteria_schema["properties"]

    def test_tool_call_count_evaluator_schemas(self) -> None:
        """Test ToolCallCountEvaluator schema generation."""
        # Test config schema
        config_schema = ToolCallCountEvaluator.get_config_schema()
        assert isinstance(config_schema, dict)
        assert "properties" in config_schema
        assert "name" in config_schema["properties"]
        assert "strict" in config_schema["properties"]

        # Test criteria schema
        criteria_schema = ToolCallCountEvaluator.get_evaluation_criteria_schema()
        assert isinstance(criteria_schema, dict)
        assert "properties" in criteria_schema
        assert "tool_calls_count" in criteria_schema["properties"]

    def test_tool_call_args_evaluator_schemas(self) -> None:
        """Test ToolCallArgsEvaluator schema generation."""
        # Test config schema
        config_schema = ToolCallArgsEvaluator.get_config_schema()
        assert isinstance(config_schema, dict)
        assert "properties" in config_schema
        assert "name" in config_schema["properties"]
        assert "strict" in config_schema["properties"]
        assert "subset" in config_schema["properties"]

        # Test criteria schema
        criteria_schema = ToolCallArgsEvaluator.get_evaluation_criteria_schema()
        assert isinstance(criteria_schema, dict)
        assert "properties" in criteria_schema
        assert "tool_calls" in criteria_schema["properties"]

    def test_tool_call_output_evaluator_schemas(self) -> None:
        """Test ToolCallOutputEvaluator schema generation."""
        # Test config schema
        config_schema = ToolCallOutputEvaluator.get_config_schema()
        assert isinstance(config_schema, dict)
        assert "properties" in config_schema
        assert "name" in config_schema["properties"]
        assert "strict" in config_schema["properties"]

        # Test criteria schema
        criteria_schema = ToolCallOutputEvaluator.get_evaluation_criteria_schema()
        assert isinstance(criteria_schema, dict)
        assert "properties" in criteria_schema
        assert "tool_outputs" in criteria_schema["properties"]

    def test_base_llm_judge_evaluator_schemas(self) -> None:
        """Test BaseLLMJudgeEvaluator schema generation."""
        # Test config schema
        config_schema = LLMJudgeMixin[
            OutputEvaluationCriteria,
            LLMJudgeOutputEvaluatorConfig,
        ].get_config_schema()
        assert isinstance(config_schema, dict)
        assert "properties" in config_schema
        assert "name" in config_schema["properties"]
        assert "prompt" in config_schema["properties"], (
            f"Prompt not found in config schema: {config_schema}"
        )
        assert "model" in config_schema["properties"]

        # Test criteria schema
        criteria_schema = LLMJudgeMixin[
            OutputEvaluationCriteria,
            LLMJudgeOutputEvaluatorConfig,
        ].get_evaluation_criteria_schema()
        assert isinstance(criteria_schema, dict)
        assert "properties" in criteria_schema
        assert "expected_output" in criteria_schema["properties"]

    def test_llm_judge_evaluator_schemas(self) -> None:
        """Test LLMJudgeEvaluator schema generation."""
        # Test config schema
        config_schema = LLMJudgeOutputEvaluator.get_config_schema()
        assert isinstance(config_schema, dict)
        assert "properties" in config_schema
        assert "name" in config_schema["properties"]
        assert "prompt" in config_schema["properties"]
        assert "model" in config_schema["properties"]
        assert "target_output_key" in config_schema["properties"]

        # Test criteria schema
        criteria_schema = LLMJudgeOutputEvaluator.get_evaluation_criteria_schema()
        assert isinstance(criteria_schema, dict)
        assert "properties" in criteria_schema
        assert "expected_output" in criteria_schema["properties"]

    def test_llm_judge_trajectory_evaluator_schemas(self) -> None:
        """Test LlmJudgeTrajectoryEvaluator schema generation."""
        # Test config schema
        config_schema = LLMJudgeTrajectoryEvaluator.get_config_schema()
        assert isinstance(config_schema, dict)
        assert "properties" in config_schema
        assert "name" in config_schema["properties"]
        assert "prompt" in config_schema["properties"]
        assert "model" in config_schema["properties"]
        assert "target_output_key" not in config_schema["properties"]

        # Test criteria schema
        criteria_schema = LLMJudgeTrajectoryEvaluator.get_evaluation_criteria_schema()
        assert isinstance(criteria_schema, dict)
        assert "properties" in criteria_schema
        assert "expected_agent_behavior" in criteria_schema["properties"]


class TestJustificationSchemas:
    """Test justification schema generation and validation for all evaluators."""

    def test_exact_match_evaluator_justification_schema(self) -> None:
        """Test ExactMatchEvaluator justification schema generation."""
        # Test justification type extraction
        justification_type = ExactMatchEvaluator._extract_justification_type()
        assert justification_type is type(None)

    def test_json_similarity_evaluator_justification_schema(self) -> None:
        """Test JsonSimilarityEvaluator justification schema generation."""
        # Test justification type extraction - JSON similarity provides str justification
        justification_type = JsonSimilarityEvaluator._extract_justification_type()
        assert justification_type is str

    def test_tool_call_order_evaluator_justification_schema(self) -> None:
        """Test ToolCallOrderEvaluator justification schema generation."""
        # Test justification type extraction - tool call evaluators have their own justification types
        from uipath.eval.evaluators.tool_call_order_evaluator import (
            ToolCallOrderEvaluatorJustification,
        )

        justification_type = ToolCallOrderEvaluator._extract_justification_type()
        assert justification_type is ToolCallOrderEvaluatorJustification

    def test_tool_call_count_evaluator_justification_schema(self) -> None:
        """Test ToolCallCountEvaluator justification schema generation."""
        # Test justification type extraction - tool call evaluators have their own justification types
        from uipath.eval.evaluators.tool_call_count_evaluator import (
            ToolCallCountEvaluatorJustification,
        )

        justification_type = ToolCallCountEvaluator._extract_justification_type()
        assert justification_type is ToolCallCountEvaluatorJustification

    def test_tool_call_args_evaluator_justification_schema(self) -> None:
        """Test ToolCallArgsEvaluator justification schema generation."""
        # Test justification type extraction - tool call evaluators have their own justification types
        from uipath.eval.evaluators.tool_call_args_evaluator import (
            ToolCallArgsEvaluatorJustification,
        )

        justification_type = ToolCallArgsEvaluator._extract_justification_type()
        assert justification_type is ToolCallArgsEvaluatorJustification

    def test_tool_call_output_evaluator_justification_schema(self) -> None:
        """Test ToolCallOutputEvaluator justification schema generation."""
        # Test justification type extraction - tool call evaluators have their own justification types
        from uipath.eval.evaluators.tool_call_output_evaluator import (
            ToolCallOutputEvaluatorJustification,
        )

        justification_type = ToolCallOutputEvaluator._extract_justification_type()
        assert justification_type is ToolCallOutputEvaluatorJustification

    def test_llm_judge_output_evaluator_justification_schema(self) -> None:
        """Test LLMJudgeOutputEvaluator justification schema generation."""
        # Test justification type extraction - LLM evaluators use str for justification
        justification_type = LLMJudgeOutputEvaluator._extract_justification_type()
        assert justification_type is str

    def test_llm_judge_trajectory_evaluator_justification_schema(self) -> None:
        """Test LLMJudgeTrajectoryEvaluator justification schema generation."""
        # Test justification type extraction - LLM evaluators use str for justification
        justification_type = LLMJudgeTrajectoryEvaluator._extract_justification_type()
        assert justification_type is str


class TestBaseEvaluatorFunctionality:
    """Test base evaluator functionality."""

    def test_type_extraction_exact_match(self) -> None:
        """Test type extraction for ExactMatchEvaluator."""
        criteria_type = ExactMatchEvaluator._extract_evaluation_criteria_type()
        config_type = ExactMatchEvaluator._extract_config_type()

        assert criteria_type == OutputEvaluationCriteria
        assert config_type == ExactMatchEvaluatorConfig

    def test_type_extraction_json_similarity(self) -> None:
        """Test type extraction for JsonSimilarityEvaluator."""
        criteria_type = JsonSimilarityEvaluator._extract_evaluation_criteria_type()
        config_type = JsonSimilarityEvaluator._extract_config_type()

        assert criteria_type == OutputEvaluationCriteria
        assert config_type == JsonSimilarityEvaluatorConfig

    def test_type_extraction_tool_call_order(self) -> None:
        """Test type extraction for ToolCallOrderEvaluator."""
        criteria_type = ToolCallOrderEvaluator._extract_evaluation_criteria_type()
        config_type = ToolCallOrderEvaluator._extract_config_type()

        assert criteria_type == ToolCallOrderEvaluationCriteria
        assert config_type == ToolCallOrderEvaluatorConfig

    def test_type_extraction_tool_call_count(self) -> None:
        """Test type extraction for ToolCallCountEvaluator."""
        criteria_type = ToolCallCountEvaluator._extract_evaluation_criteria_type()
        config_type = ToolCallCountEvaluator._extract_config_type()

        assert criteria_type == ToolCallCountEvaluationCriteria
        assert config_type == ToolCallCountEvaluatorConfig

    def test_type_extraction_tool_call_args(self) -> None:
        """Test type extraction for ToolCallArgsEvaluator."""
        criteria_type = ToolCallArgsEvaluator._extract_evaluation_criteria_type()
        config_type = ToolCallArgsEvaluator._extract_config_type()

        assert criteria_type == ToolCallArgsEvaluationCriteria
        assert config_type == ToolCallArgsEvaluatorConfig

    def test_type_extraction_tool_call_output(self) -> None:
        """Test type extraction for ToolCallOutputEvaluator."""
        criteria_type = ToolCallOutputEvaluator._extract_evaluation_criteria_type()
        config_type = ToolCallOutputEvaluator._extract_config_type()

        assert criteria_type == ToolCallOutputEvaluationCriteria
        assert config_type == ToolCallOutputEvaluatorConfig

    def test_config_validation_exact_match(self) -> None:
        """Test config validation for ExactMatchEvaluator."""
        # Valid config - create minimal required config
        config_dict = {
            "name": "TestEvaluator",
            "case_sensitive": True,
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"config": config_dict, "id": str(uuid.uuid4())}
        )

        assert isinstance(evaluator.evaluator_config, ExactMatchEvaluatorConfig)
        assert evaluator.evaluator_config.name == "TestEvaluator"
        assert evaluator.evaluator_config.case_sensitive is True

    def test_criteria_validation_exact_match(self) -> None:
        """Test criteria validation for ExactMatchEvaluator."""
        config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"config": config_dict, "id": str(uuid.uuid4())}
        )

        # Test dict validation
        criteria_dict = {"expected_output": "test output"}
        validated = evaluator.validate_evaluation_criteria(criteria_dict)

        assert isinstance(validated, OutputEvaluationCriteria)
        assert validated.expected_output == "test output"

    def test_criteria_validation_tool_call_order(self) -> None:
        """Test criteria validation for ToolCallOrderEvaluator."""
        config_dict = {
            "name": "Test",
            "strict": False,
            "default_evaluation_criteria": {"tool_calls_order": ["tool1", "tool2"]},
        }
        evaluator = ToolCallOrderEvaluator.model_validate(
            {"config": config_dict, "id": str(uuid.uuid4())}
        )

        # Test dict validation
        criteria_dict = {"tool_calls_order": ["tool1", "tool2", "tool3"]}
        validated = evaluator.validate_evaluation_criteria(criteria_dict)

        assert isinstance(validated, ToolCallOrderEvaluationCriteria)
        assert validated.tool_calls_order == ["tool1", "tool2", "tool3"]

    def test_config_validation_tool_call_output(self) -> None:
        """Test config validation for ToolCallOutputEvaluator."""
        # Valid config - create minimal required config
        config_dict = {
            "name": "TestToolOutputEvaluator",
            "strict": True,
            "default_evaluation_criteria": {
                "tool_outputs": [{"name": "tool1", "output": "output1"}]
            },
        }
        evaluator = ToolCallOutputEvaluator.model_validate(
            {"config": config_dict, "id": str(uuid.uuid4())}
        )

        assert isinstance(evaluator.evaluator_config, ToolCallOutputEvaluatorConfig)
        assert evaluator.evaluator_config.name == "TestToolOutputEvaluator"
        assert evaluator.evaluator_config.strict is True

    def test_criteria_validation_tool_call_output(self) -> None:
        """Test criteria validation for ToolCallOutputEvaluator."""
        config_dict = {
            "name": "Test",
            "strict": False,
            "default_evaluation_criteria": {
                "tool_outputs": [{"name": "tool1", "output": "output1"}]
            },
        }
        evaluator = ToolCallOutputEvaluator.model_validate(
            {"config": config_dict, "id": str(uuid.uuid4())}
        )

        # Test dict validation
        criteria_dict = {
            "tool_outputs": [
                {"name": "tool1", "output": "output1"},
                {"name": "tool2", "output": "output2"},
            ]
        }
        validated = evaluator.validate_evaluation_criteria(criteria_dict)

        assert isinstance(validated, ToolCallOutputEvaluationCriteria)
        assert len(validated.tool_outputs) == 2
        assert validated.tool_outputs[0].name == "tool1"
        assert validated.tool_outputs[0].output == "output1"
        assert validated.tool_outputs[1].name == "tool2"
        assert validated.tool_outputs[1].output == "output2"

    def test_criteria_validation_llm_judge_output(self, mocker: MockerFixture) -> None:
        """Test criteria validation for LLMJudgeOutputEvaluator."""
        config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
            "model": "gpt-4o-2024-08-06",
        }
        mock_llm_service = mocker.MagicMock()
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {
                "config": config_dict,
                "llm_service": mock_llm_service,
                "id": str(uuid.uuid4()),
            }
        )

        # Test dict validation
        criteria_dict = {"expected_output": "test output"}
        validated = evaluator.validate_evaluation_criteria(criteria_dict)

        assert isinstance(validated, OutputEvaluationCriteria)
        assert validated.expected_output == "test output"

    def test_automatic_type_detection(self) -> None:
        """Test that types are automatically detected from Generic parameters."""
        # Create evaluator - test with basic evaluators that don't trigger CLI imports
        config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        evaluator = JsonSimilarityEvaluator.model_validate(
            {"config": config_dict, "id": str(uuid.uuid4())}
        )

        # Types should be set correctly
        assert evaluator.evaluation_criteria_type == OutputEvaluationCriteria
        assert evaluator.config_type.__name__ == "JsonSimilarityEvaluatorConfig"

    def test_justification_validation_none_type(self) -> None:
        """Test justification validation for evaluators with None justification type."""
        config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"config": config_dict, "id": str(uuid.uuid4())}
        )

        # Test None validation
        assert evaluator.validate_justification(None) is None
        assert evaluator.validate_justification("any string") is None

    def test_justification_validation_str_type(self, mocker: MockerFixture) -> None:
        """Test justification validation for evaluators with str justification type."""
        config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
            "model": "gpt-4o-2024-08-06",
        }
        mock_llm_service = mocker.MagicMock()
        evaluator = LLMJudgeOutputEvaluator.model_validate(
            {
                "config": config_dict,
                "llm_service": mock_llm_service,
                "id": str(uuid.uuid4()),
            }
        )

        # Test string validation
        assert (
            evaluator.validate_justification("test justification")
            == "test justification"
        )
        assert evaluator.validate_justification(123) == "123"
        assert evaluator.validate_justification(None) == ""

    def test_justification_type_consistency(self, mocker: MockerFixture) -> None:
        """Test that justification_type field matches the generic parameter."""
        # Test None type evaluators
        config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        exact_match_evaluator = ExactMatchEvaluator.model_validate(
            {"config": config_dict, "id": str(uuid.uuid4())}
        )
        assert exact_match_evaluator.justification_type is type(None)

        # Test str type evaluators
        llm_config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
            "model": "gpt-4o-2024-08-06",
        }
        mock_llm_service = mocker.MagicMock()
        llm_evaluator = LLMJudgeOutputEvaluator.model_validate(
            {
                "config": llm_config_dict,
                "llm_service": mock_llm_service,
                "id": str(uuid.uuid4()),
            }
        )
        assert llm_evaluator.justification_type is str


class TestEvaluatorInstances:
    """Test evaluator instance functionality."""

    def test_instance_config_access(self) -> None:
        """Test that evaluator instances have properly typed config access."""
        config_data = {
            "name": "TestEvaluator",
            "case_sensitive": False,
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        evaluator = ExactMatchEvaluator.model_validate(
            {"config": config_data, "id": str(uuid.uuid4())}
        )

        # Test direct config access
        assert evaluator.evaluator_config.name == "TestEvaluator"
        assert evaluator.evaluator_config.case_sensitive is False

        # Verify type
        assert isinstance(evaluator.evaluator_config, ExactMatchEvaluatorConfig)

    def test_instance_schema_access(self) -> None:
        """Test that evaluator instances can access schemas."""
        config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        evaluator = JsonSimilarityEvaluator.model_validate(
            {"config": config_dict, "id": str(uuid.uuid4())}
        )

        # Should be able to get schemas from instances
        config_schema = evaluator.get_config_schema()
        criteria_schema = evaluator.get_evaluation_criteria_schema()

        assert isinstance(config_schema, dict)
        assert isinstance(criteria_schema, dict)
        assert "properties" in config_schema
        assert "properties" in criteria_schema


class TestEvaluatorReference:
    """Test EvaluatorReference model functionality."""

    def test_evaluator_reference_from_string(self) -> None:
        """Test creating EvaluatorReference from a string."""
        from uipath._cli._evals._models._evaluation_set import EvaluatorReference

        ref = EvaluatorReference.model_validate("evaluator-id-123")
        assert ref.ref == "evaluator-id-123"
        assert ref.weight == 1.0

    def test_evaluator_reference_from_dict_with_weight(self) -> None:
        """Test creating EvaluatorReference from a dict with weight."""
        from uipath._cli._evals._models._evaluation_set import EvaluatorReference

        ref = EvaluatorReference.model_validate(
            {"ref": "evaluator-id-123", "weight": 2.5}
        )
        assert ref.ref == "evaluator-id-123"
        assert ref.weight == 2.5

    def test_evaluator_reference_from_dict_without_weight(self) -> None:
        """Test creating EvaluatorReference from a dict without weight."""
        from uipath._cli._evals._models._evaluation_set import EvaluatorReference

        ref = EvaluatorReference.model_validate({"ref": "evaluator-id-123"})
        assert ref.ref == "evaluator-id-123"
        assert ref.weight == 1.0

    def test_evaluator_reference_serialization_with_weight(self) -> None:
        """Test serializing EvaluatorReference with weight."""
        from uipath._cli._evals._models._evaluation_set import EvaluatorReference

        ref = EvaluatorReference(ref="evaluator-id-123", weight=2.5)
        serialized = ref.model_dump(mode="json")
        assert serialized == {"ref": "evaluator-id-123", "weight": 2.5}

    def test_evaluator_reference_serialization_without_weight(self) -> None:
        """Test serializing EvaluatorReference without weight."""
        from uipath._cli._evals._models._evaluation_set import EvaluatorReference

        ref = EvaluatorReference(ref="evaluator-id-123")
        serialized = ref.model_dump(mode="json")
        assert serialized == "evaluator-id-123"

    def test_evaluator_reference_weight_validation(self) -> None:
        """Test that weight must be non-negative."""
        from uipath._cli._evals._models._evaluation_set import EvaluatorReference

        # Valid weight
        ref = EvaluatorReference.model_validate(
            {"ref": "evaluator-id-123", "weight": 0}
        )
        assert ref.weight == 0

        # Invalid negative weight should raise error
        with pytest.raises(ValidationError):
            EvaluatorReference.model_validate({"ref": "evaluator-id-123", "weight": -1})

    def test_evaluation_set_with_evaluator_references(self) -> None:
        """Test EvaluationSet with EvaluatorReference objects in evaluatorConfigs."""
        from uipath._cli._evals._models._evaluation_set import EvaluationSet

        eval_set_data = {
            "id": "test-set-123",
            "name": "Test Evaluation Set",
            "version": "1.0",
            "evaluatorConfigs": [
                "evaluator-1",
                {"ref": "evaluator-2", "weight": 2.0},
                {"ref": "evaluator-3", "weight": 1.5},
            ],
            "evaluations": [],
        }

        eval_set = EvaluationSet.model_validate(eval_set_data)
        assert len(eval_set.evaluator_configs) == 3
        assert eval_set.evaluator_configs[0].ref == "evaluator-1"
        assert eval_set.evaluator_configs[0].weight == 1.0
        assert eval_set.evaluator_configs[1].ref == "evaluator-2"
        assert eval_set.evaluator_configs[1].weight == 2.0
        assert eval_set.evaluator_configs[2].ref == "evaluator-3"
        assert eval_set.evaluator_configs[2].weight == 1.5

    def test_evaluation_set_backward_compatibility(self) -> None:
        """Test EvaluationSet with old evaluatorRefs field (backward compatibility)."""
        from uipath._cli._evals._models._evaluation_set import EvaluationSet

        eval_set_data = {
            "id": "test-set-456",
            "name": "Legacy Evaluation Set",
            "version": "1.0",
            "evaluatorRefs": ["evaluator-1", "evaluator-2", "evaluator-3"],
            "evaluations": [],
        }

        eval_set = EvaluationSet.model_validate(eval_set_data)
        assert len(eval_set.evaluator_refs) == 3
        assert eval_set.evaluator_refs[0] == "evaluator-1"
        assert eval_set.evaluator_refs[1] == "evaluator-2"
        assert eval_set.evaluator_refs[2] == "evaluator-3"
        # evaluator_configs should be empty when using old field
        assert len(eval_set.evaluator_configs) == 0
