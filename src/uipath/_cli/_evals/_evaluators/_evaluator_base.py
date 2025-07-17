from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

from uipath._cli._evals._models import (
    EvaluationResult,
    EvaluatorCategory,
    EvaluatorType,
)


@dataclass
class EvaluatorBaseParams:
    """Parameters for initializing the base evaluator."""

    evaluator_id: str
    category: EvaluatorCategory
    evaluator_type: EvaluatorType
    name: str
    description: str
    created_at: str
    updated_at: str
    target_output_key: str


class EvaluatorBase(ABC):
    """Abstract base class for all evaluators."""

    def __init__(self):
        # initialization done via 'from_params' function
        self.id = None
        self.name = None
        self.description = None
        self.created_at = None
        self.updated_at = None
        self.category = None
        self.type = None
        self.target_output_key = None
        pass

    @classmethod
    def from_params(cls, params: EvaluatorBaseParams, **kwargs):
        """Initialize the base evaluator from parameters.

        Args:
            params: EvaluatorBaseParams containing base configuration
            **kwargs: Additional specific parameters for concrete evaluators

        Returns:
            Initialized evaluator instance
        """
        instance = cls(**kwargs)
        instance.id = params.evaluator_id
        instance.category = params.category
        instance.type = params.evaluator_type
        instance.name = params.name
        instance.description = params.description
        instance.created_at = params.created_at
        instance.updated_at = params.updated_at
        instance.target_output_key = params.target_output_key
        return instance

    @abstractmethod
    async def evaluate(
        self,
        evaluation_id: str,
        evaluation_name: str,
        input_data: Dict[str, Any],
        expected_output: Dict[str, Any],
        actual_output: Dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate the given data and return a result.

        Args:
            evaluation_id: The ID of the evaluation being processed
            evaluation_name: The name of the evaluation
            input_data: The input data for the evaluation
            expected_output: The expected output
            actual_output: The actual output from the agent

        Returns:
            EvaluationResult containing the score and details
        """
        pass

    def __repr__(self) -> str:
        """String representation of the evaluator."""
        return f"{self.__class__.__name__}(id='{self.id}', name='{self.name}', category={self.category.name})"  # type: ignore
