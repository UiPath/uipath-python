from typing import Any, Dict

from uipath.eval.evaluators import (
    BaseEvaluator,
    ExactMatchEvaluator,
    JsonSimilarityEvaluator,
    LlmAsAJudgeEvaluator,
    TrajectoryEvaluator,
)
from uipath.eval.models import EvaluatorCategory, EvaluatorType

from ._models import EvaluatorBaseParams


class EvaluatorFactory:
    """Factory class for creating evaluator instances based on configuration."""

    @staticmethod
    def create_evaluator(data: Dict[str, Any]) -> BaseEvaluator:
        """Create an evaluator instance from configuration data.

        Args:
            data: Dictionary containing evaluator configuration from JSON file

        Returns:
            Appropriate evaluator instance based on category

        Raises:
            ValueError: If category is unknown or required fields are missing
        """
        # Extract common fields
        evaluator_id = data.get("id")
        if not evaluator_id:
            raise ValueError("Evaluator configuration must include 'id' field")

        category = EvaluatorCategory.from_int(data.get("category"))
        evaluator_type = EvaluatorType.from_int(data.get("type", EvaluatorType.Unknown))
        name = data.get("name", "")
        description = data.get("description", "")
        created_at = data.get("createdAt", "")
        updated_at = data.get("updatedAt", "")
        target_output_key = data.get("targetOutputKey", "")

        # Create base parameters
        base_params = EvaluatorBaseParams(
            evaluator_id=evaluator_id,
            category=category,
            evaluator_type=evaluator_type,
            name=name,
            description=description,
            created_at=created_at,
            updated_at=updated_at,
            target_output_key=target_output_key,
        )

        # Create evaluator based on category
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
