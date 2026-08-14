"""Tests for evaluator factory functionality.

This module tests:
- EvaluatorFactory.create_evaluator() with various configurations
- Flexible name and description field handling (top-level vs config-level)
- Field precedence when specified in multiple locations
- Proper instantiation across all evaluator types
"""

import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_mock.plugin import MockerFixture

from uipath.eval.evaluators.contains_evaluator import ContainsEvaluator
from uipath.eval.evaluators.evaluator_factory import EvaluatorFactory
from uipath.eval.evaluators.exact_match_evaluator import ExactMatchEvaluator
from uipath.eval.evaluators.json_similarity_evaluator import JsonSimilarityEvaluator
from uipath.eval.evaluators.llm_judge_output_evaluator import LLMJudgeOutputEvaluator
from uipath.eval.evaluators.llm_judge_trajectory_evaluator import (
    LLMJudgeTrajectoryEvaluator,
    LLMJudgeTrajectorySimulationEvaluator,
)
from uipath.eval.evaluators.tool_call_args_evaluator import ToolCallArgsEvaluator
from uipath.eval.evaluators.tool_call_count_evaluator import ToolCallCountEvaluator
from uipath.eval.evaluators.tool_call_order_evaluator import ToolCallOrderEvaluator
from uipath.eval.evaluators.tool_call_output_evaluator import ToolCallOutputEvaluator


class TestEvaluatorFactoryFieldHandling:
    """Test field handling (name, description) in evaluator factory."""

    @pytest.fixture
    def base_exact_match_config(self) -> dict[str, Any]:
        """Base configuration for ExactMatchEvaluator."""
        return {
            "version": "1.0",
            "id": "TestExactMatch",
            "evaluatorTypeId": "uipath-exact-match",
            "evaluatorConfig": {
                "targetOutputKey": "*",
                "negated": False,
                "ignoreCase": False,
            },
        }

    def test_name_in_config_only(self, base_exact_match_config: dict[str, Any]) -> None:
        """Test that name specified in evaluatorConfig is correctly set.

        Args:
            base_exact_match_config: Base evaluator configuration fixture
        """
        base_exact_match_config["evaluatorConfig"]["name"] = "NameFromConfig"

        evaluator = EvaluatorFactory.create_evaluator(base_exact_match_config)

        assert isinstance(evaluator, ExactMatchEvaluator)
        assert evaluator.name == "NameFromConfig"

    def test_name_at_top_level_only(
        self, base_exact_match_config: dict[str, Any]
    ) -> None:
        """Test that name specified at top level is correctly merged into config.

        Args:
            base_exact_match_config: Base evaluator configuration fixture
        """
        base_exact_match_config["name"] = "NameFromTopLevel"

        evaluator = EvaluatorFactory.create_evaluator(base_exact_match_config)

        assert isinstance(evaluator, ExactMatchEvaluator)
        assert evaluator.name == "NameFromTopLevel"

    def test_name_in_both_locations_top_level_wins(
        self, base_exact_match_config: dict[str, Any]
    ) -> None:
        """Test that top-level name takes precedence over config-level name.

        Args:
            base_exact_match_config: Base evaluator configuration fixture
        """
        base_exact_match_config["name"] = "TopLevelName"
        base_exact_match_config["evaluatorConfig"]["name"] = "ConfigLevelName"

        evaluator = EvaluatorFactory.create_evaluator(base_exact_match_config)

        assert isinstance(evaluator, ExactMatchEvaluator)
        assert evaluator.name == "TopLevelName"

    def test_description_in_config_only(
        self, base_exact_match_config: dict[str, Any]
    ) -> None:
        """Test that description specified in evaluatorConfig is correctly set.

        Args:
            base_exact_match_config: Base evaluator configuration fixture
        """
        base_exact_match_config["evaluatorConfig"]["name"] = "TestEvaluator"
        base_exact_match_config["evaluatorConfig"]["description"] = (
            "Description from config"
        )

        evaluator = EvaluatorFactory.create_evaluator(base_exact_match_config)

        assert isinstance(evaluator, ExactMatchEvaluator)
        assert evaluator.description == "Description from config"

    def test_description_at_top_level_only(
        self, base_exact_match_config: dict[str, Any]
    ) -> None:
        """Test that description specified at top level is correctly merged into config.

        Args:
            base_exact_match_config: Base evaluator configuration fixture
        """
        base_exact_match_config["name"] = "TestEvaluator"
        base_exact_match_config["description"] = "Description from top level"

        evaluator = EvaluatorFactory.create_evaluator(base_exact_match_config)

        assert isinstance(evaluator, ExactMatchEvaluator)
        assert evaluator.description == "Description from top level"

    def test_description_in_both_locations_top_level_wins(
        self, base_exact_match_config: dict[str, Any]
    ) -> None:
        """Test that top-level description takes precedence over config-level description.

        Args:
            base_exact_match_config: Base evaluator configuration fixture
        """
        base_exact_match_config["name"] = "TestEvaluator"
        base_exact_match_config["description"] = "Top level description"
        base_exact_match_config["evaluatorConfig"]["description"] = (
            "Config level description"
        )

        evaluator = EvaluatorFactory.create_evaluator(base_exact_match_config)

        assert isinstance(evaluator, ExactMatchEvaluator)
        assert evaluator.description == "Top level description"

    def test_both_name_and_description_at_top_level(
        self, base_exact_match_config: dict[str, Any]
    ) -> None:
        """Test that both name and description can be specified at top level.

        Args:
            base_exact_match_config: Base evaluator configuration fixture
        """
        base_exact_match_config["name"] = "CustomName"
        base_exact_match_config["description"] = "Custom description"

        evaluator = EvaluatorFactory.create_evaluator(base_exact_match_config)

        assert isinstance(evaluator, ExactMatchEvaluator)
        assert evaluator.name == "CustomName"
        assert evaluator.description == "Custom description"

    def test_no_name_or_description_uses_defaults(
        self, base_exact_match_config: dict[str, Any]
    ) -> None:
        """Test that evaluator uses defaults when name/description not specified.

        Args:
            base_exact_match_config: Base evaluator configuration fixture
        """
        evaluator = EvaluatorFactory.create_evaluator(base_exact_match_config)

        assert isinstance(evaluator, ExactMatchEvaluator)
        # Name should have a default from the config class
        assert evaluator.name is not None
        # Description defaults to empty string
        assert evaluator.description == ""

    def test_empty_string_values_are_handled_correctly(
        self, base_exact_match_config: dict[str, Any]
    ) -> None:
        """Test that empty string values for name/description are handled properly.

        Args:
            base_exact_match_config: Base evaluator configuration fixture
        """
        base_exact_match_config["name"] = ""
        base_exact_match_config["description"] = ""
        base_exact_match_config["evaluatorConfig"]["name"] = "ConfigName"
        base_exact_match_config["evaluatorConfig"]["description"] = "ConfigDescription"

        evaluator = EvaluatorFactory.create_evaluator(base_exact_match_config)

        assert isinstance(evaluator, ExactMatchEvaluator)
        # Empty strings should still override (top-level takes precedence)
        assert evaluator.name == ""
        assert evaluator.description == ""


class TestEvaluatorFactoryAcrossTypes:
    """Test that field handling works consistently across all evaluator types."""

    @pytest.mark.parametrize(
        "evaluator_type_id,expected_class",
        [
            ("uipath-exact-match", ExactMatchEvaluator),
            ("uipath-contains", ContainsEvaluator),
            ("uipath-json-similarity", JsonSimilarityEvaluator),
            ("uipath-tool-call-count", ToolCallCountEvaluator),
            ("uipath-tool-call-order", ToolCallOrderEvaluator),
            ("uipath-tool-call-args", ToolCallArgsEvaluator),
            ("uipath-tool-call-output", ToolCallOutputEvaluator),
        ],
    )
    def test_top_level_name_and_description_across_evaluator_types(
        self, evaluator_type_id: str, expected_class: type
    ) -> None:
        """Test that top-level name and description work for various evaluator types.

        Args:
            evaluator_type_id: The evaluator type identifier
            expected_class: The expected evaluator class type
        """
        config = {
            "version": "1.0",
            "id": f"Test{evaluator_type_id}",
            "name": f"Custom{evaluator_type_id}Name",
            "description": f"Custom {evaluator_type_id} description",
            "evaluatorTypeId": evaluator_type_id,
            "evaluatorConfig": {},
        }

        evaluator = EvaluatorFactory.create_evaluator(config)

        assert isinstance(evaluator, expected_class)
        assert evaluator.name == f"Custom{evaluator_type_id}Name"
        assert evaluator.description == f"Custom {evaluator_type_id} description"

    def test_llm_judge_output_evaluator_field_handling(
        self, mocker: "MockerFixture"
    ) -> None:
        """Test field handling for LLMJudgeOutputEvaluator.

        Args:
            mocker: Pytest mock fixture
        """
        # Mock the UiPath SDK to avoid needing credentials
        mock_llm_service = mocker.MagicMock()
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.LLMJudgeMixin._get_llm_service",
            return_value=mock_llm_service,
        )

        config = {
            "version": "1.0",
            "id": "TestLLMJudgeOutput",
            "name": "CustomLLMJudgeName",
            "description": "Custom LLM judge description",
            "evaluatorTypeId": "uipath-llm-judge-output-semantic-similarity",
            "evaluatorConfig": {
                "model": "gpt-4",
                "temperature": 0.0,
            },
        }

        evaluator = EvaluatorFactory.create_evaluator(config)

        assert isinstance(evaluator, LLMJudgeOutputEvaluator)
        assert evaluator.name == "CustomLLMJudgeName"
        assert evaluator.description == "Custom LLM judge description"

    def test_llm_judge_trajectory_evaluator_field_handling(
        self, mocker: "MockerFixture"
    ) -> None:
        """Test field handling for LLMJudgeTrajectoryEvaluator.

        Args:
            mocker: Pytest mock fixture
        """
        # Mock the UiPath SDK to avoid needing credentials
        mock_llm_service = mocker.MagicMock()
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.LLMJudgeMixin._get_llm_service",
            return_value=mock_llm_service,
        )

        config = {
            "version": "1.0",
            "id": "TestLLMJudgeTrajectory",
            "name": "CustomTrajectoryName",
            "description": "Custom trajectory description",
            "evaluatorTypeId": "uipath-llm-judge-trajectory-similarity",
            "evaluatorConfig": {
                "model": "gpt-4",
                "temperature": 0.0,
            },
        }

        evaluator = EvaluatorFactory.create_evaluator(config)

        assert isinstance(evaluator, LLMJudgeTrajectoryEvaluator)
        assert evaluator.name == "CustomTrajectoryName"
        assert evaluator.description == "Custom trajectory description"

    def test_llm_judge_trajectory_simulation_evaluator_field_handling(
        self, mocker: "MockerFixture"
    ) -> None:
        """Test field handling for LLMJudgeTrajectorySimulationEvaluator.

        Args:
            mocker: Pytest mock fixture
        """
        # Mock the UiPath SDK to avoid needing credentials
        mock_llm_service = mocker.MagicMock()
        mocker.patch(
            "uipath.eval.evaluators.llm_as_judge_evaluator.LLMJudgeMixin._get_llm_service",
            return_value=mock_llm_service,
        )

        config = {
            "version": "1.0",
            "id": "TestLLMJudgeTrajectorySimulation",
            "name": "CustomSimulationName",
            "description": "Custom simulation description",
            "evaluatorTypeId": "uipath-llm-judge-trajectory-simulation",
            "evaluatorConfig": {
                "model": "gpt-4",
                "temperature": 0.0,
            },
        }

        evaluator = EvaluatorFactory.create_evaluator(config)

        assert isinstance(evaluator, LLMJudgeTrajectorySimulationEvaluator)
        assert evaluator.name == "CustomSimulationName"
        assert evaluator.description == "Custom simulation description"


class TestEvaluatorFactoryPrepareConfig:
    """Test the _prepare_evaluator_config helper method."""

    def test_prepare_config_empty_input(self) -> None:
        """Test _prepare_evaluator_config with empty input."""
        result = EvaluatorFactory._prepare_evaluator_config({})

        assert isinstance(result, dict)
        assert result == {}

    def test_prepare_config_only_evaluator_config(self) -> None:
        """Test _prepare_evaluator_config with only evaluatorConfig."""
        data = {
            "evaluatorConfig": {
                "name": "TestName",
                "description": "TestDescription",
                "someOtherField": "value",
            }
        }

        result = EvaluatorFactory._prepare_evaluator_config(data)

        assert result == {
            "name": "TestName",
            "description": "TestDescription",
            "someOtherField": "value",
        }

    def test_prepare_config_top_level_overrides(self) -> None:
        """Test that top-level fields override config-level fields."""
        data = {
            "name": "TopLevelName",
            "description": "TopLevelDescription",
            "evaluatorConfig": {
                "name": "ConfigName",
                "description": "ConfigDescription",
                "otherField": "value",
            },
        }

        result = EvaluatorFactory._prepare_evaluator_config(data)

        assert result["name"] == "TopLevelName"
        assert result["description"] == "TopLevelDescription"
        assert result["otherField"] == "value"

    def test_prepare_config_preserves_other_fields(self) -> None:
        """Test that other config fields are preserved."""
        data = {
            "name": "NewName",
            "evaluatorConfig": {
                "name": "OldName",
                "targetOutputKey": "*",
                "caseSensitive": False,
                "nested": {"key": "value"},
            },
        }

        result = EvaluatorFactory._prepare_evaluator_config(data)

        assert result["name"] == "NewName"
        assert result["targetOutputKey"] == "*"
        assert result["caseSensitive"] is False
        assert result["nested"] == {"key": "value"}

    def test_prepare_config_handles_non_dict_evaluator_config(self) -> None:
        """Test that non-dict evaluatorConfig is handled gracefully."""
        data = {"name": "TestName", "evaluatorConfig": "not a dict"}

        result = EvaluatorFactory._prepare_evaluator_config(data)

        assert isinstance(result, dict)
        assert result["name"] == "TestName"


class TestEvaluatorFactoryPropertyAccess:
    """Test that name and description properties work after factory instantiation."""

    def test_property_getters_work(self) -> None:
        """Test that property getters return correct values."""
        config = {
            "version": "1.0",
            "id": "TestEvaluator",
            "name": "InitialName",
            "description": "Initial description",
            "evaluatorTypeId": "uipath-exact-match",
            "evaluatorConfig": {},
        }

        evaluator = EvaluatorFactory.create_evaluator(config)

        # Test getters
        assert evaluator.name == "InitialName"
        assert evaluator.description == "Initial description"

    def test_property_setters_work(self) -> None:
        """Test that property setters correctly update values."""
        config = {
            "version": "1.0",
            "id": "TestEvaluator",
            "name": "InitialName",
            "description": "Initial description",
            "evaluatorTypeId": "uipath-exact-match",
            "evaluatorConfig": {},
        }

        evaluator = EvaluatorFactory.create_evaluator(config)

        # Test setters
        evaluator.name = "UpdatedName"
        evaluator.description = "Updated description"

        assert evaluator.name == "UpdatedName"
        assert evaluator.description == "Updated description"


class TestCustomCodedEvaluatorModuleLoading:
    """Custom-coded evaluators must load their module once, without leaking sys.modules."""

    @staticmethod
    def _write_evaluator_module(path: Path) -> None:
        path.write_text(
            "from uipath.eval.evaluators.exact_match_evaluator import ExactMatchEvaluator\n"
            "\n"
            "class MyCustomEvaluator(ExactMatchEvaluator):\n"
            "    pass\n"
        )

    @staticmethod
    def _config(module_path: Path) -> dict[str, Any]:
        return {
            "version": "1.0",
            "id": "TestCustom",
            "evaluatorTypeId": "uipath-exact-match",
            "evaluatorSchema": f"file://{module_path}:MyCustomEvaluator",
            "evaluatorConfig": {
                "targetOutputKey": "*",
                "negated": False,
                "ignoreCase": False,
            },
        }

    def test_module_is_cached_and_not_leaked(self, tmp_path: Path) -> None:
        """Repeated creation from the same file reuses one cached module.

        Regression test: the module name previously embedded ``id(data)`` (a fresh
        dict per call), so every ``create_evaluator`` call re-executed the module
        and leaked a new entry into ``sys.modules`` — unbounded growth (and O(n^2)
        cost) when evaluators are built per datapoint. The module must now load
        once and be reused.
        """
        module_path = tmp_path / "my_custom_eval.py"
        self._write_evaluator_module(module_path)

        def custom_module_keys() -> set[str]:
            return {k for k in sys.modules if k.startswith("_custom_evaluator_")}

        before = custom_module_keys()
        try:
            first = EvaluatorFactory.create_evaluator(self._config(module_path))
            after_first = custom_module_keys()
            second = EvaluatorFactory.create_evaluator(self._config(module_path))
            third = EvaluatorFactory.create_evaluator(self._config(module_path))
            after_third = custom_module_keys()

            # Same class object across calls => the module was loaded once and reused.
            assert type(first) is type(second) is type(third)
            # Exactly one module added, and no further growth on subsequent calls.
            assert len(after_first) == len(before) + 1
            assert after_third == after_first
        finally:
            for key in custom_module_keys() - before:
                del sys.modules[key]

    def test_failed_load_is_not_cached(self, tmp_path: Path) -> None:
        """A module that raises during import must not be left cached.

        The exec-failure branch pops the half-initialized module from sys.modules
        so a fixed file can be retried in the same process; without it the broken
        load would be sticky (the path-keyed cache short-circuits the retry).
        """
        module_path = tmp_path / "broken_eval.py"
        module_path.write_text("raise RuntimeError('boom at import time')\n")

        def custom_module_keys() -> set[str]:
            return {k for k in sys.modules if k.startswith("_custom_evaluator_")}

        before = custom_module_keys()
        config = self._config(module_path)
        try:
            with pytest.raises(ValueError):
                EvaluatorFactory.create_evaluator(config)
            # The failed load left nothing cached, so the same path can be retried.
            assert custom_module_keys() == before

            # Fix the file; a subsequent create for the same path must now succeed.
            self._write_evaluator_module(module_path)
            evaluator = EvaluatorFactory.create_evaluator(self._config(module_path))
            assert type(evaluator).__name__ == "MyCustomEvaluator"
        finally:
            for key in custom_module_keys() - before:
                del sys.modules[key]

    def test_same_stem_in_different_dirs_do_not_collide(self, tmp_path: Path) -> None:
        """Two custom-evaluator files sharing a basename load as distinct modules.

        The path hash in the module name is what disambiguates them; a stem-only
        key would return the first file's class for both.
        """
        path_a = tmp_path / "a" / "my_eval.py"
        path_b = tmp_path / "b" / "my_eval.py"
        path_a.parent.mkdir()
        path_b.parent.mkdir()
        self._write_evaluator_module(path_a)
        self._write_evaluator_module(path_b)

        def custom_module_keys() -> set[str]:
            return {k for k in sys.modules if k.startswith("_custom_evaluator_")}

        before = custom_module_keys()
        try:
            eval_a = EvaluatorFactory.create_evaluator(self._config(path_a))
            eval_b = EvaluatorFactory.create_evaluator(self._config(path_b))
            # Distinct files => distinct cached modules => distinct class objects.
            assert type(eval_a) is not type(eval_b)
            assert len(custom_module_keys() - before) == 2
        finally:
            for key in custom_module_keys() - before:
                del sys.modules[key]

    def test_path_traversal_is_rejected(self) -> None:
        """A schema path with '..' segments is refused before any file load."""
        config = {
            "version": "1.0",
            "id": "TestTraversal",
            "evaluatorTypeId": "uipath-exact-match",
            "evaluatorSchema": "file://../../../etc/passwd:MyCustomEvaluator",
            "evaluatorConfig": {
                "targetOutputKey": "*",
                "negated": False,
                "ignoreCase": False,
            },
        }
        with pytest.raises(ValueError, match="must not contain"):
            EvaluatorFactory.create_evaluator(config)
