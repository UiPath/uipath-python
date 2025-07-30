from typing import Any, Dict

from .._models import EvaluatorCategory, EvaluatorType
from ._agent_scorer_evaluator import AgentScorerEvaluator
from ._deterministic_evaluator import DeterministicEvaluator
from ._evaluator_base import EvaluatorBase, EvaluatorBaseParams
from ._llm_as_judge_evaluator import LlmAsAJudgeEvaluator
from ._trajectory_evaluator import TrajectoryEvaluator


class EvaluatorFactory:
    """Factory class for creating evaluator instances based on configuration."""

    @staticmethod
    def create_evaluator(data: Dict[str, Any]) -> EvaluatorBase:
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
        if category == EvaluatorCategory.Deterministic:
            return EvaluatorFactory._create_deterministic_evaluator(base_params, data)
        elif category == EvaluatorCategory.LlmAsAJudge:
            return EvaluatorFactory._create_llm_as_judge_evaluator(base_params, data)
        elif category == EvaluatorCategory.AgentScorer:
            return EvaluatorFactory._create_agent_scorer_evaluator(base_params, data)
        elif category == EvaluatorCategory.Trajectory:
            return EvaluatorFactory._create_trajectory_evaluator(base_params, data)
        else:
            raise ValueError(f"Unknown evaluator category: {category}")

    @staticmethod
    def _create_deterministic_evaluator(
        base_params: EvaluatorBaseParams, data: Dict[str, Any]
    ) -> DeterministicEvaluator:
        """Create a deterministic evaluator."""
        raise NotImplementedError()

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

        return LlmAsAJudgeEvaluator.from_params(
            base_params,
            prompt=prompt,
            model=model,
            target_output_key=data.get("targetOutputKey", "*"),
        )

    @staticmethod
    def _create_agent_scorer_evaluator(
        base_params: EvaluatorBaseParams, data: Dict[str, Any]
    ) -> AgentScorerEvaluator:
        """Create an agent scorer evaluator."""
        raise NotImplementedError()

    @staticmethod
    def _create_trajectory_evaluator(
        base_params: EvaluatorBaseParams, data: Dict[str, Any]
    ) -> TrajectoryEvaluator:
        """Create a trajectory evaluator."""
        raise NotImplementedError()
