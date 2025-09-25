from typing import Any, Dict

from pydantic import TypeAdapter

from uipath._cli._evals._models._evaluator import (
    EqualsEvaluatorParams,
    Evaluator,
    JsonSimilarityEvaluatorParams,
    LLMEvaluatorParams,
    TrajectoryEvaluatorParams,
)
from uipath._cli._evals._models._evaluator_base_params import EvaluatorBaseParams
from uipath.eval.evaluators import (
    BaseEvaluator,
    ExactMatchEvaluator,
    JsonSimilarityEvaluator,
    LlmAsAJudgeEvaluator,
    TrajectoryEvaluator,
)


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

        params: EvaluatorBaseParams = TypeAdapter(Evaluator).validate_python(data)

        match params:
            case EqualsEvaluatorParams():
                return EvaluatorFactory._create_exact_match_evaluator(params)
            case JsonSimilarityEvaluatorParams():
                return EvaluatorFactory._create_json_similarity_evaluator(params)
            case LLMEvaluatorParams():
                return EvaluatorFactory._create_llm_as_judge_evaluator(params)
            case TrajectoryEvaluatorParams():
                return EvaluatorFactory._create_trajectory_evaluator(params)
            case _:
                raise ValueError(f"Unknown evaluator category: {params}")

    @staticmethod
    def _create_exact_match_evaluator(
        params: EqualsEvaluatorParams,
    ) -> ExactMatchEvaluator:
        """Create a deterministic evaluator."""
        return ExactMatchEvaluator(**params.model_dump())

    @staticmethod
    def _create_json_similarity_evaluator(
        params: JsonSimilarityEvaluatorParams,
    ) -> JsonSimilarityEvaluator:
        """Create a deterministic evaluator."""
        return JsonSimilarityEvaluator(**params.model_dump())

    @staticmethod
    def _create_llm_as_judge_evaluator(
        params: LLMEvaluatorParams,
    ) -> LlmAsAJudgeEvaluator:
        """Create an LLM-as-a-judge evaluator."""
        if not params.prompt:
            raise ValueError("LLM evaluator must include 'prompt' field")

        if not params.model:
            raise ValueError("LLM evaluator must include 'model' field")
        if params.model == "same-as-agent":
            raise ValueError(
                "'same-as-agent' model option is not supported by coded agents evaluations. Please select a specific model for the evaluator."
            )

        return LlmAsAJudgeEvaluator(**params.model_dump())

    @staticmethod
    def _create_trajectory_evaluator(
        params: TrajectoryEvaluatorParams,
    ) -> TrajectoryEvaluator:
        """Create a trajectory evaluator."""
        if not params.prompt:
            raise ValueError("Trajectory evaluator must include 'prompt' field")

        if not params.model:
            raise ValueError("LLM evaluator must include 'model' field")
        if params.model == "same-as-agent":
            raise ValueError(
                "'same-as-agent' model option is not supported by coded agents evaluations. Please select a specific model for the evaluator."
            )

        return TrajectoryEvaluator(**params.model_dump())
