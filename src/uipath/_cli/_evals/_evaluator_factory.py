import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from uipath._cli._evals._helpers import (  # type: ignore # Remove after gnarly fix
    try_extract_file_and_class_name,
)
from uipath._cli._evals._models._evaluator import (
    EvaluatorConfig,
    LegacyEqualsEvaluatorParams,
    LegacyEvaluator,
    LegacyJsonSimilarityEvaluatorParams,
    LegacyLLMEvaluatorParams,
    LegacyTrajectoryEvaluatorParams,
)
from uipath._cli._evals._models._evaluator_base_params import EvaluatorBaseParams
from uipath._utils.constants import EVALS_FOLDER
from uipath.eval.evaluators import (
    BaseEvaluator,
    LegacyBaseEvaluator,
    LegacyContextPrecisionEvaluator,
    LegacyExactMatchEvaluator,
    LegacyFaithfulnessEvaluator,
    LegacyJsonSimilarityEvaluator,
    LegacyLlmAsAJudgeEvaluator,
    LegacyTrajectoryEvaluator,
)
from uipath.eval.evaluators.base_evaluator import BaseEvaluatorConfig
from uipath.eval.evaluators.contains_evaluator import (
    ContainsEvaluator,
    ContainsEvaluatorConfig,
)
from uipath.eval.evaluators.exact_match_evaluator import (
    ExactMatchEvaluator,
    ExactMatchEvaluatorConfig,
)
from uipath.eval.evaluators.json_similarity_evaluator import (
    JsonSimilarityEvaluator,
    JsonSimilarityEvaluatorConfig,
)
from uipath.eval.evaluators.llm_judge_output_evaluator import (
    LLMJudgeOutputEvaluator,
    LLMJudgeOutputEvaluatorConfig,
    LLMJudgeStrictJSONSimilarityOutputEvaluator,
    LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig,
)
from uipath.eval.evaluators.llm_judge_trajectory_evaluator import (
    LLMJudgeTrajectoryEvaluator,
    LLMJudgeTrajectoryEvaluatorConfig,
    LLMJudgeTrajectorySimulationEvaluator,
    LLMJudgeTrajectorySimulationEvaluatorConfig,
)
from uipath.eval.evaluators.tool_call_args_evaluator import (
    ToolCallArgsEvaluator,
    ToolCallArgsEvaluatorConfig,
)
from uipath.eval.evaluators.tool_call_count_evaluator import (
    ToolCallCountEvaluator,
    ToolCallCountEvaluatorConfig,
)
from uipath.eval.evaluators.tool_call_order_evaluator import (
    ToolCallOrderEvaluator,
    ToolCallOrderEvaluatorConfig,
)
from uipath.eval.evaluators.tool_call_output_evaluator import (
    ToolCallOutputEvaluator,
    ToolCallOutputEvaluatorConfig,
)
from uipath.eval.models import LegacyEvaluatorType

logger = logging.getLogger(__name__)

EVALUATOR_SCHEMA_TO_EVALUATOR_CLASS = {
    ContainsEvaluatorConfig: ContainsEvaluator,
    ExactMatchEvaluatorConfig: ExactMatchEvaluator,
    JsonSimilarityEvaluatorConfig: JsonSimilarityEvaluator,
    LLMJudgeOutputEvaluatorConfig: LLMJudgeOutputEvaluator,
    LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig: LLMJudgeStrictJSONSimilarityOutputEvaluator,
    LLMJudgeTrajectoryEvaluatorConfig: LLMJudgeTrajectoryEvaluator,
    LLMJudgeTrajectorySimulationEvaluatorConfig: LLMJudgeTrajectorySimulationEvaluator,
    ToolCallArgsEvaluatorConfig: ToolCallArgsEvaluator,
    ToolCallCountEvaluatorConfig: ToolCallCountEvaluator,
    ToolCallOrderEvaluatorConfig: ToolCallOrderEvaluator,
    ToolCallOutputEvaluatorConfig: ToolCallOutputEvaluator,
}


class EvaluatorFactory:
    """Factory class for creating evaluator instances based on configuration."""

    @staticmethod
    def _prepare_evaluator_config(data: dict[str, Any]) -> dict[str, Any]:
        """Prepare evaluator config by merging top-level fields into evaluatorConfig.

        This allows flexibility in specifying fields like 'name' and 'description' either at the
        top level or within evaluatorConfig. Top-level values take precedence if both exist.

        Args:
            data: The raw evaluator data dictionary

        Returns:
            The prepared evaluatorConfig with merged fields
        """
        evaluator_config = data.get("evaluatorConfig", {})
        if not isinstance(evaluator_config, dict):
            evaluator_config = {}
        else:
            # Create a copy to avoid modifying the original
            evaluator_config = evaluator_config.copy()

        # Merge top-level 'name' into config if present
        if "name" in data and data["name"] is not None:
            # Top-level name takes precedence
            evaluator_config["name"] = data["name"]

        # Merge top-level 'description' into config if present
        if "description" in data and data["description"] is not None:
            # Top-level description takes precedence
            evaluator_config["description"] = data["description"]

        return evaluator_config

    @classmethod
    def create_evaluator(
        cls,
        data: dict[str, Any],
        evaluators_dir: Path | None = None,
        agent_model: str | None = None,
    ) -> BaseEvaluator[Any, Any, Any]:
        if data.get("version", None) == "1.0":
            return cls._create_evaluator_internal(data, evaluators_dir)
        else:
            return cls._create_legacy_evaluator_internal(data, agent_model)

    @staticmethod
    def _create_evaluator_internal(
        data: dict[str, Any],
        evaluators_dir: Path | None = None,
    ) -> BaseEvaluator[Any, Any, Any]:
        # check custom evaluator
        evaluator_schema = data.get("evaluatorSchema", "")
        success, file_path, class_name = try_extract_file_and_class_name(
            evaluator_schema
        )
        if success:
            return EvaluatorFactory._create_coded_evaluator_internal(
                data, file_path, class_name, evaluators_dir
            )

        config: BaseEvaluatorConfig[Any] = TypeAdapter(EvaluatorConfig).validate_python(
            data
        )
        evaluator_class = EVALUATOR_SCHEMA_TO_EVALUATOR_CLASS.get(type(config))
        if not evaluator_class:
            raise ValueError(f"Unknown evaluator configuration: {config}")
        return TypeAdapter(evaluator_class).validate_python(
            {
                "id": data.get("id"),
                "config": EvaluatorFactory._prepare_evaluator_config(data),
            }
        )

    @staticmethod
    def _create_coded_evaluator_internal(
        data: dict[str, Any],
        file_path_str: str,
        class_name: str,
        evaluators_dir: Path | None = None,
    ) -> BaseEvaluator[Any, Any, Any]:
        """Create a coded evaluator by dynamically loading from a Python file.

        Args:
            data: Dictionary containing evaluator configuration with evaluatorTypeId
                  in format "file://path/to/file.py:ClassName"
            evaluators_dir: Directory containing evaluator configuration files

        Returns:
            Instance of the dynamically loaded evaluator class

        Raises:
            ValueError: If file or class cannot be loaded, or if the class is not a BaseEvaluator subclass
        """
        file_path = Path(file_path_str)
        if not file_path.is_absolute():
            if not file_path.exists():
                if evaluators_dir is not None:
                    # Try the file directly in evaluators_dir first
                    file_path = evaluators_dir / file_path_str
                    if not file_path.exists():
                        # Fall back to evaluators_dir/custom/
                        file_path = evaluators_dir / "custom" / file_path_str
                else:
                    # Fall back to the old behavior
                    file_path = (
                        Path.cwd()
                        / EVALS_FOLDER
                        / "evaluators"
                        / "custom"
                        / file_path_str
                    )

        if not file_path.exists():
            raise ValueError(
                f"Evaluator file not found: {file_path}. "
                f"Make sure the file exists in the evaluators/custom/ directory"
            )

        module_name = f"_custom_evaluator_{file_path.stem}_{id(data)}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Could not load module from {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise ValueError(
                f"Error executing module from {file_path}: {str(e)}"
            ) from e

        # Get the class from the module
        if not hasattr(module, class_name):
            raise ValueError(
                f"Class '{class_name}' not found in {file_path}. "
                f"Available classes: {[name for name in dir(module) if not name.startswith('_')]}"
            )

        evaluator_class = getattr(module, class_name)

        if not isinstance(evaluator_class, type) or not issubclass(
            evaluator_class, BaseEvaluator
        ):
            raise ValueError(
                f"Class '{class_name}' must be a subclass of BaseEvaluator"
            )

        evaluator_id = data.get("id")
        if not evaluator_id or not isinstance(evaluator_id, str):
            raise ValueError("Evaluator 'id' must be a non-empty string")
        return TypeAdapter(evaluator_class).validate_python(
            {
                "id": evaluator_id,
                "config": EvaluatorFactory._prepare_evaluator_config(data),
            }
        )

    @staticmethod
    def _create_legacy_evaluator_internal(
        data: dict[str, Any],
        agent_model: str | None = None,
    ) -> LegacyBaseEvaluator[Any]:
        """Create an evaluator instance from configuration data.

        Args:
            data: Dictionary containing evaluator configuration from JSON file
            agent_model: Optional model name from agent settings for resolving
                'same-as-agent' model configuration

        Returns:
            Appropriate evaluator instance based on category

        Raises:
            ValueError: If category is unknown or required fields are missing
        """
        params: EvaluatorBaseParams = TypeAdapter(LegacyEvaluator).validate_python(data)

        match params:
            case LegacyEqualsEvaluatorParams():
                return EvaluatorFactory._create_legacy_exact_match_evaluator(params)
            case LegacyJsonSimilarityEvaluatorParams():
                return EvaluatorFactory._create_legacy_json_similarity_evaluator(params)
            case LegacyLLMEvaluatorParams():
                return EvaluatorFactory._create_legacy_llm_as_judge_evaluator(
                    params, agent_model
                )
            case LegacyTrajectoryEvaluatorParams():
                return EvaluatorFactory._create_legacy_trajectory_evaluator(
                    params, agent_model
                )
            case _:
                raise ValueError(f"Unknown evaluator category: {params}")

    @staticmethod
    def _create_legacy_exact_match_evaluator(
        params: LegacyEqualsEvaluatorParams,
    ) -> LegacyExactMatchEvaluator:
        """Create a deterministic evaluator."""
        return LegacyExactMatchEvaluator(**params.model_dump(), config={})

    @staticmethod
    def _create_legacy_json_similarity_evaluator(
        params: LegacyJsonSimilarityEvaluatorParams,
    ) -> LegacyJsonSimilarityEvaluator:
        """Create a deterministic evaluator."""
        return LegacyJsonSimilarityEvaluator(**params.model_dump(), config={})

    @staticmethod
    def _create_legacy_llm_as_judge_evaluator(
        params: LegacyLLMEvaluatorParams,
        agent_model: str | None = None,
    ) -> LegacyBaseEvaluator[Any]:
        """Create an LLM-as-a-judge evaluator or context precision evaluator based on type."""
        if not params.model:
            raise ValueError("LLM evaluator must include 'model' field")

        # Resolve 'same-as-agent' to actual agent model
        if params.model == "same-as-agent":
            if not agent_model:
                raise ValueError(
                    "'same-as-agent' model option requires agent settings. "
                    "Ensure agent.json contains valid model settings."
                )
            logger.info(
                f"Resolving 'same-as-agent' to agent model: {agent_model} "
                f"for evaluator '{params.name}'"
            )
            params = params.model_copy(update={"model": agent_model})

        # Check evaluator type to determine which evaluator to create
        if params.evaluator_type == LegacyEvaluatorType.ContextPrecision:
            return LegacyContextPrecisionEvaluator(**params.model_dump(), config={})
        elif params.evaluator_type == LegacyEvaluatorType.Faithfulness:
            return LegacyFaithfulnessEvaluator(**params.model_dump(), config={})
        else:
            if not params.prompt:
                raise ValueError("LLM evaluator must include 'prompt' field")

            return LegacyLlmAsAJudgeEvaluator(**params.model_dump(), config={})

    @staticmethod
    def _create_legacy_trajectory_evaluator(
        params: LegacyTrajectoryEvaluatorParams,
        agent_model: str | None = None,
    ) -> LegacyTrajectoryEvaluator:
        """Create a trajectory evaluator."""
        if not params.prompt:
            raise ValueError("Trajectory evaluator must include 'prompt' field")

        if not params.model:
            raise ValueError("Trajectory evaluator must include 'model' field")

        # Resolve 'same-as-agent' to actual agent model
        if params.model == "same-as-agent":
            if not agent_model:
                raise ValueError(
                    "'same-as-agent' model option requires agent settings. "
                    "Ensure agent.json contains valid model settings."
                )
            logger.info(
                f"Resolving 'same-as-agent' to agent model: {agent_model} "
                f"for evaluator '{params.name}'"
            )
            params = params.model_copy(update={"model": agent_model})

        logger.info(
            f"Creating trajectory evaluator '{params.name}' with model: {params.model}"
        )
        return LegacyTrajectoryEvaluator(**params.model_dump(), config={})
