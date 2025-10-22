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
from uipath.eval.evaluators import (
    BaseEvaluator,
    LegacyBaseEvaluator,
    LegacyExactMatchEvaluator,
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
            case JsonSimilarityEvaluatorConfig():
                return EvaluatorFactory._create_json_similarity_evaluator(data)
            case LLMJudgeOutputEvaluatorConfig():
                return EvaluatorFactory._create_llm_judge_output_evaluator(data)
            case LLMJudgeStrictJSONSimilarityOutputEvaluatorConfig():
                return EvaluatorFactory._create_llm_judge_strict_json_similarity_output_evaluator(
                    data
                )
            case LLMJudgeTrajectoryEvaluatorConfig():
                return EvaluatorFactory._create_trajectory_evaluator(data)
            case ToolCallArgsEvaluatorConfig():
                return EvaluatorFactory._create_tool_call_args_evaluator(data)
            case ToolCallCountEvaluatorConfig():
                return EvaluatorFactory._create_tool_call_count_evaluator(data)
            case ToolCallOrderEvaluatorConfig():
                return EvaluatorFactory._create_tool_call_order_evaluator(data)
            case ToolCallOutputEvaluatorConfig():
                return EvaluatorFactory._create_tool_call_output_evaluator(data)
            case LLMJudgeTrajectorySimulationEvaluatorConfig():
                return (
                    EvaluatorFactory._create_llm_judge_simulation_trajectory_evaluator(
                        data
                    )
                )
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
    def _create_json_similarity_evaluator(
        data: Dict[str, Any],
    ) -> JsonSimilarityEvaluator:
        return JsonSimilarityEvaluator(
            id=data.get("id"),
            config=data.get("evaluatorConfig"),
        )  # type: ignore

    @staticmethod
    def _create_llm_judge_output_evaluator(
        data: Dict[str, Any],
    ) -> LLMJudgeOutputEvaluator:
        return LLMJudgeOutputEvaluator(
            id=data.get("id"),
            config=data.get("evaluatorConfig"),
        )  # type: ignore

    @staticmethod
    def _create_llm_judge_strict_json_similarity_output_evaluator(
        data: Dict[str, Any],
    ) -> LLMJudgeStrictJSONSimilarityOutputEvaluator:
        return LLMJudgeStrictJSONSimilarityOutputEvaluator(
            id=data.get("id"),
            config=data.get("evaluatorConfig"),
        )  # type: ignore

    @staticmethod
    def _create_trajectory_evaluator(
        data: Dict[str, Any],
    ) -> LLMJudgeTrajectoryEvaluator:
        return LLMJudgeTrajectoryEvaluator(
            id=data.get("id"),
            config=data.get("evaluatorConfig"),
        )  # type: ignore

    @staticmethod
    def _create_tool_call_args_evaluator(
        data: Dict[str, Any],
    ) -> ToolCallArgsEvaluator:
        return ToolCallArgsEvaluator(
            id=data.get("id"),
            config=data.get("evaluatorConfig"),
        )  # type: ignore

    @staticmethod
    def _create_tool_call_count_evaluator(
        data: Dict[str, Any],
    ) -> ToolCallCountEvaluator:
        return ToolCallCountEvaluator(
            id=data.get("id"),
            config=data.get("evaluatorConfig"),
        )  # type: ignore

    @staticmethod
    def _create_tool_call_order_evaluator(
        data: Dict[str, Any],
    ) -> ToolCallOrderEvaluator:
        return ToolCallOrderEvaluator(
            id=data.get("id"),
            config=data.get("evaluatorConfig"),
        )  # type: ignore

    @staticmethod
    def _create_tool_call_output_evaluator(
        data: Dict[str, Any],
    ) -> ToolCallOutputEvaluator:
        return ToolCallOutputEvaluator(
            id=data.get("id"),
            config=data.get("evaluatorConfig"),
        )  # type: ignore

    @staticmethod
    def _create_llm_judge_simulation_trajectory_evaluator(
        data: Dict[str, Any],
    ) -> LLMJudgeTrajectorySimulationEvaluator:
        return LLMJudgeTrajectorySimulationEvaluator(
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
    ) -> LegacyJsonSimilarityEvaluator:
        """Create a deterministic evaluator."""
        return LegacyJsonSimilarityEvaluator(**params.model_dump())

    @staticmethod
    def _create_legacy_llm_as_judge_evaluator(
        params: LLMEvaluatorParams,
    ) -> LegacyLlmAsAJudgeEvaluator:
        """Create an LLM-as-a-judge evaluator."""
        if not params.prompt:
            raise ValueError("LLM evaluator must include 'prompt' field")

        if not params.model:
            raise ValueError("LLM evaluator must include 'model' field")
        if params.model == "same-as-agent":
            raise ValueError(
                "'same-as-agent' model option is not supported by coded agents evaluations. Please select a specific model for the evaluator."
            )

        return LegacyLlmAsAJudgeEvaluator(**params.model_dump())

    @staticmethod
    def _create_legacy_trajectory_evaluator(
        params: TrajectoryEvaluatorParams,
    ) -> LegacyTrajectoryEvaluator:
        """Create a trajectory evaluator."""
        if not params.prompt:
            raise ValueError("Trajectory evaluator must include 'prompt' field")

        if not params.model:
            raise ValueError("LLM evaluator must include 'model' field")
        if params.model == "same-as-agent":
            raise ValueError(
                "'same-as-agent' model option is not supported by coded agents evaluations. Please select a specific model for the evaluator."
            )

        return LegacyTrajectoryEvaluator(**params.model_dump())
