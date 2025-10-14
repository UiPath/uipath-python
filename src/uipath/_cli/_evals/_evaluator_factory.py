from typing import Any, Dict

from pydantic import TypeAdapter

from uipath._cli._evals._models._evaluation_set import AnyEvaluator
from uipath._cli._evals._models._evaluator import (
    EqualsEvaluatorParams,
    EvaluatorConfig,
    JsonSimilarityEvaluatorParams,
    LegacyEvaluator,
    LLMEvaluatorParams,
    TrajectoryEvaluatorParams,
)
from uipath._cli._evals._models._evaluator_base_params import EvaluatorBaseParams
from uipath.eval.coded_evaluators import BaseEvaluator
from uipath.eval.coded_evaluators.base_evaluator import BaseEvaluatorConfig
from uipath.eval.coded_evaluators.contains_evaluator import (
    ContainsEvaluator,
    ContainsEvaluatorConfig,
)
from uipath.eval.coded_evaluators.exact_match_evaluator import (
    ExactMatchEvaluator,
    ExactMatchEvaluatorConfig,
)
from uipath.eval.evaluators import (
    JsonSimilarityEvaluator,
    LegacyBaseEvaluator,
    LegacyExactMatchEvaluator,
    LlmAsAJudgeEvaluator,
    TrajectoryEvaluator,
)


class EvaluatorFactory:
    """Factory class for creating evaluator instances based on configuration."""

    @classmethod
    def create_evaluator(cls, data: Dict[str, Any]) -> AnyEvaluator:
        if data.get("version", None) == "1.0":
            return cls._create_evaluator_internal(data)
        return cls._create_legacy_evaluator_internal(data)

    @staticmethod
    def _create_evaluator_internal(
        data: Dict[str, Any],
    ) -> BaseEvaluator[Any, Any, Any]:
        config: BaseEvaluatorConfig[Any] = TypeAdapter(EvaluatorConfig).validate_python(
            data
        )
        match config:
            case ContainsEvaluatorConfig():
                return EvaluatorFactory._create_contains_evaluator(data)
            case ExactMatchEvaluatorConfig():
                return EvaluatorFactory._create_exact_match_evaluator(data)
            case _:
                raise ValueError(f"Unknown evaluator configuration: {config}")

    @staticmethod
    def _create_contains_evaluator(data: Dict[str, Any]) -> ContainsEvaluator:
        return ContainsEvaluator(
            id=data.get("id"),
            config=data.get("evaluatorConfig"),
        )  # type: ignore

    @staticmethod
    def _create_exact_match_evaluator(
        data: Dict[str, Any],
    ) -> ExactMatchEvaluator:
        return ExactMatchEvaluator(
            id=data.get("id"),
            config=data.get("evaluatorConfig"),
        )  # type: ignore

    @staticmethod
    def _create_legacy_evaluator_internal(
        data: Dict[str, Any],
    ) -> LegacyBaseEvaluator[Any]:
        """Create an evaluator instance from configuration data.

        Args:
            data: Dictionary containing evaluator configuration from JSON file

        Returns:
            Appropriate evaluator instance based on category

        Raises:
            ValueError: If category is unknown or required fields are missing
        """
        params: EvaluatorBaseParams = TypeAdapter(LegacyEvaluator).validate_python(data)

        match params:
            case EqualsEvaluatorParams():
                return EvaluatorFactory._create_legacy_exact_match_evaluator(params)
            case JsonSimilarityEvaluatorParams():
                return EvaluatorFactory._create_legacy_json_similarity_evaluator(params)
            case LLMEvaluatorParams():
                return EvaluatorFactory._create_legacy_llm_as_judge_evaluator(params)
            case TrajectoryEvaluatorParams():
                return EvaluatorFactory._create_legacy_trajectory_evaluator(params)
            case _:
                raise ValueError(f"Unknown evaluator category: {params}")

    @staticmethod
    def _create_legacy_exact_match_evaluator(
        params: EqualsEvaluatorParams,
    ) -> LegacyExactMatchEvaluator:
        """Create a deterministic evaluator."""
        return LegacyExactMatchEvaluator(**params.model_dump())

    @staticmethod
    def _create_legacy_json_similarity_evaluator(
        params: JsonSimilarityEvaluatorParams,
    ) -> JsonSimilarityEvaluator:
        """Create a deterministic evaluator."""
        return JsonSimilarityEvaluator(**params.model_dump())

    @staticmethod
    def _create_legacy_llm_as_judge_evaluator(
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
    def _create_legacy_trajectory_evaluator(
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
