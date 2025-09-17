from typing import Any, Dict

from uipath._cli._evals._models._evaluator_base_params import EvaluatorBaseParams
from uipath.eval.evaluators import (
    BaseEvaluator,
    ExactMatchEvaluator,
    JsonSimilarityEvaluator,
    LlmAsAJudgeEvaluator,
    TrajectoryEvaluator,
)
from uipath.eval.models.models import EvaluatorCategory, EvaluatorType


class EvaluatorFactory:
    """Factory class for creating evaluator instances based on configuration."""

    @classmethod
    def create_evaluator(cls, data: Dict[str, Any]) -> BaseEvaluator[Any]:
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
        id = data.get("id", "")
        if not id:
            raise ValueError("Evaluator configuration must include 'id' field")

        category = EvaluatorCategory.from_int(data.get("category"))
        evaluator_type = EvaluatorType.from_int(data.get("type", EvaluatorType.Unknown))
        description = data.get("description", "")
        created_at = data.get("createdAt", "")
        updated_at = data.get("updatedAt", "")
        target_output_key = data.get("targetOutputKey", "")

        # Create base parameters
        base_params = EvaluatorBaseParams(
            id=id,
            category=category,
            evaluator_type=evaluator_type,
            name=name,
            description=description,
            created_at=created_at,
            updated_at=updated_at,
            target_output_key=target_output_key,
        )

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
        return ExactMatchEvaluator(
            **base_params.model_dump(),
        )

    @staticmethod
    def _create_json_similarity_evaluator(
        base_params: EvaluatorBaseParams, data: Dict[str, Any]
    ) -> JsonSimilarityEvaluator:
        """Create a deterministic evaluator."""
        return JsonSimilarityEvaluator(
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

        return LlmAsAJudgeEvaluator(
            **base_params.model_dump(),
            prompt=prompt,
            model=model,
        )

    @staticmethod
    def _create_trajectory_evaluator(
        base_params: EvaluatorBaseParams, data: Dict[str, Any]
    ) -> TrajectoryEvaluator[Any]:
        """Create a trajectory evaluator."""
        raise NotImplementedError()
