"""Tests for evaluator schema functionality and base evaluator features.

This module tests:
- Config schema generation for all evaluators
- Evaluation criteria schema generation for all evaluators
- Base evaluator functionality (type extraction, validation)
- Generic type parameter handling
"""

from typing import Any

import pytest
from pytest_mock.plugin import MockerFixture

from src.uipath.eval.coded_evaluators.exact_match_evaluator import (
    ExactMatchEvaluator,
    ExactMatchEvaluatorConfig,
)
from src.uipath.eval.coded_evaluators.json_similarity_evaluator import (
    JsonSimilarityEvaluator,
    JsonSimilarityEvaluatorConfig,
)
from src.uipath.eval.coded_evaluators.llm_as_judge_evaluator import (
    LLMJudgeMixin,
)
from src.uipath.eval.coded_evaluators.llm_judge_output_evaluator import (
    LLMJudgeOutputEvaluator,
    LLMJudgeOutputEvaluatorConfig,
)
from src.uipath.eval.coded_evaluators.llm_judge_trajectory_evaluator import (
    LLMJudgeTrajectoryEvaluator,
)
from src.uipath.eval.coded_evaluators.output_evaluator import (
    OutputEvaluationCriteria,
)
from src.uipath.eval.coded_evaluators.tool_call_args_evaluator import (
    ToolCallArgsEvaluationCriteria,
    ToolCallArgsEvaluator,
    ToolCallArgsEvaluatorConfig,
)
from src.uipath.eval.coded_evaluators.tool_call_count_evaluator import (
    ToolCallCountEvaluationCriteria,
    ToolCallCountEvaluator,
    ToolCallCountEvaluatorConfig,
)
from src.uipath.eval.coded_evaluators.tool_call_order_evaluator import (
    ToolCallOrderEvaluationCriteria,
    ToolCallOrderEvaluator,
    ToolCallOrderEvaluatorConfig,
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

    def test_config_validation_exact_match(self) -> None:
        """Test config validation for ExactMatchEvaluator."""
        # Valid config - create minimal required config
        config_dict = {
            "name": "TestEvaluator",
            "case_sensitive": True,
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        evaluator = ExactMatchEvaluator.model_validate({"config": config_dict})

        assert isinstance(evaluator.evaluator_config, ExactMatchEvaluatorConfig)
        assert evaluator.evaluator_config.name == "TestEvaluator"
        assert evaluator.evaluator_config.case_sensitive is True

    def test_criteria_validation_exact_match(self) -> None:
        """Test criteria validation for ExactMatchEvaluator."""
        config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        evaluator = ExactMatchEvaluator.model_validate({"config": config_dict})

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
        evaluator = ToolCallOrderEvaluator.model_validate({"config": config_dict})

        # Test dict validation
        criteria_dict = {"tool_calls_order": ["tool1", "tool2", "tool3"]}
        validated = evaluator.validate_evaluation_criteria(criteria_dict)

        assert isinstance(validated, ToolCallOrderEvaluationCriteria)
        assert validated.tool_calls_order == ["tool1", "tool2", "tool3"]

    def test_criteria_validation_llm_judge_output(self, mocker: MockerFixture) -> None:
        """Test criteria validation for LLMJudgeOutputEvaluator."""

        # Mock the UiPath constructor to avoid authentication
        mock_uipath = mocker.MagicMock()
        mock_llm = mocker.MagicMock()
        mock_uipath.llm = mock_llm

        # Mock the chat completions response as an async method
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(
                message=mocker.MagicMock(
                    content='{"score": 80, "justification": "Good response that meets criteria"}'
                )
            )
        ]

        # Make chat_completions an async method
        async def mock_chat_completions(*args: Any, **kwargs: Any) -> Any:
            return mock_response

        mock_llm.chat_completions = mock_chat_completions

        # Mock the UiPath import and constructor
        mocker.patch("uipath.UiPath", return_value=mock_uipath)
        config_dict = {
            "name": "Test",
            "default_evaluation_criteria": {"expected_output": "test"},
            "model": "gpt-4o-2024-08-06",
        }
        evaluator = LLMJudgeOutputEvaluator.model_validate({"config": config_dict})

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
        evaluator = JsonSimilarityEvaluator.model_validate({"config": config_dict})

        # Types should be set correctly
        assert evaluator.evaluation_criteria_type == OutputEvaluationCriteria
        assert evaluator.config_type.__name__ == "JsonSimilarityEvaluatorConfig"


class TestEvaluatorInstances:
    """Test evaluator instance functionality."""

    def test_instance_config_access(self) -> None:
        """Test that evaluator instances have properly typed config access."""
        config_data = {
            "name": "TestEvaluator",
            "case_sensitive": False,
            "default_evaluation_criteria": {"expected_output": "test"},
        }
        evaluator = ExactMatchEvaluator.model_validate({"config": config_data})

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
        evaluator = JsonSimilarityEvaluator.model_validate({"config": config_dict})

        # Should be able to get schemas from instances
        config_schema = evaluator.get_config_schema()
        criteria_schema = evaluator.get_evaluation_criteria_schema()

        assert isinstance(config_schema, dict)
        assert isinstance(criteria_schema, dict)
        assert "properties" in config_schema
        assert "properties" in criteria_schema
