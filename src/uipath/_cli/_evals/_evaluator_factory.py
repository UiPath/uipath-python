import os
from pathlib import Path
from typing import Any, Dict
import importlib.util
import inspect

from uipath.eval.evaluators import (
    BaseEvaluator,
    ExactMatchEvaluator,
    JsonSimilarityEvaluator,
    LlmAsAJudgeEvaluator,
    TrajectoryEvaluator,
)
from uipath.eval.models import EvaluatorCategory, EvaluatorType

from ._models import EvaluatorBaseParams
from ..._utils.constants import PLATFORM_EVALUATOR_PREFIX

class EvaluatorFactory:
    """Factory class for creating evaluator instances based on configuration."""

    coded_evals_dir_path: Path = os.path.join("evals", "evaluators", "coded")

    @classmethod
    def create_evaluator(cls, data: Dict[str, Any]) -> BaseEvaluator:
        """Create an evaluator instance from configuration data.

        Args:
            data: Dictionary containing evaluator configuration from JSON file

        Returns:
            Appropriate evaluator instance based on category

        Raises:
            ValueError: If category is unknown or required fields are missing
        """
        # Extract common fields
        name = data.get("name", "")
        if not name:
            raise ValueError("Evaluator configuration must include 'name' field")

        category = EvaluatorCategory.from_int(data.get("category"))
        evaluator_type = EvaluatorType.from_int(data.get("type", EvaluatorType.Unknown))
        description = data.get("description", "")
        created_at = data.get("createdAt", "")
        updated_at = data.get("updatedAt", "")
        target_output_key = data.get("targetOutputKey", "")

        # Create base parameters
        base_params = EvaluatorBaseParams(
            category=category,
            evaluator_type=evaluator_type,
            name=name,
            description=description,
            created_at=created_at,
            updated_at=updated_at,
            target_output_key=target_output_key,
        )

        if name.lower().startswith(PLATFORM_EVALUATOR_PREFIX.lower()):
            match category:
                case EvaluatorCategory.Deterministic:
                    if evaluator_type == evaluator_type.Equals:
                        return EvaluatorFactory._create_exact_match_evaluator(
                            base_params, data
                        )
                    elif evaluator_type == evaluator_type.JsonSimilarity:
                        return EvaluatorFactory._create_json_similarity_evaluator(
                            base_params, data
                        )
                    else:
                        raise ValueError(
                            f"Unknown evaluator type {evaluator_type} for category {category}"
                        )
                case EvaluatorCategory.LlmAsAJudge:
                    return EvaluatorFactory._create_llm_as_judge_evaluator(
                        base_params, data
                    )
                case EvaluatorCategory.AgentScorer:
                    raise NotImplementedError()
                case EvaluatorCategory.Trajectory:
                    return EvaluatorFactory._create_trajectory_evaluator(base_params, data)
                case _:
                    raise ValueError(f"Unknown evaluator category: {category}")

        # this is a coded evaluator
        coded_evaluator_file_path = os.path.join(os.getcwd(), cls.coded_evals_dir_path, f"{name}.py")
        return EvaluatorFactory._load_coded_evaluator(coded_evaluator_file_path, base_params)

    @staticmethod
    def _load_coded_evaluator(file_path: str, base_params: EvaluatorBaseParams) -> BaseEvaluator:
        """Load a custom evaluator from a Python file.

        Args:
            file_path: Path to the Python file containing the evaluator class

        Returns:
            Instance of the custom evaluator class

        Raises:
            FileNotFoundError: If the file doesn't exist
            ImportError: If the file can't be imported
            ValueError: If no BaseEvaluator subclass is found in the file
        """
        spec = importlib.util.spec_from_file_location("custom_evaluator", file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load module from {file_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseEvaluator) and obj is not BaseEvaluator:
                # Extract class name and docstring
                class_name = obj.__name__
                class_description = obj.__doc__.strip() if obj.__doc__ else None

                return obj(
                    name=class_name,
                    description=class_description,
                )

        raise ValueError(f"No BaseEvaluator subclass found in {file_path}")


    @staticmethod
    def _create_exact_match_evaluator(
        base_params: EvaluatorBaseParams, data: Dict[str, Any]
    ) -> ExactMatchEvaluator:
        """Create a deterministic evaluator."""
        return ExactMatchEvaluator.from_params(
            **base_params.model_dump(),
        )

    @staticmethod
    def _create_json_similarity_evaluator(
        base_params: EvaluatorBaseParams, data: Dict[str, Any]
    ) -> JsonSimilarityEvaluator:
        """Create a deterministic evaluator."""
        return JsonSimilarityEvaluator.from_params(
            **base_params.model_dump(),
        )

    @staticmethod
    def _create_llm_as_judge_evaluator(
        base_params: EvaluatorBaseParams, data: Dict[str, Any]
    ) -> LlmAsAJudgeEvaluator:
        """Create an LLM-as-a-judge evaluator."""
        prompt = data.get("prompt", "")
        if not prompt:
            raise ValueError("LLM evaluator must include 'prompt' field")

        model = data.get("model", "")
        if not model:
            raise ValueError("LLM evaluator must include 'model' field")
        if model == "same-as-agent":
            raise ValueError(
                "'same-as-agent' model option is not supported by coded agents evaluations. Please select a specific model for the evaluator."
            )

        return LlmAsAJudgeEvaluator.from_params(
            **base_params.model_dump(),
            prompt=prompt,
            model=model,
        )

    @staticmethod
    def _create_trajectory_evaluator(
        base_params: EvaluatorBaseParams, data: Dict[str, Any]
    ) -> TrajectoryEvaluator:
        """Create a trajectory evaluator."""
        raise NotImplementedError()
