import functools
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

from uipath._cli._evals._models import (
    EvaluationResult,
    EvaluatorCategory,
    EvaluatorType,
)


def measure_execution_time(func):
    """Decorator to measure execution time and update EvaluationResult.evaluation_time."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> EvaluationResult:
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time

        result.evaluation_time = execution_time
        return result

    return wrapper


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
        self.id: str
        self.name: str
        self.description: str
        self.created_at: str
        self.updated_at: str
        self.category: EvaluatorCategory
        self.type: EvaluatorType
        self.target_output_key: str
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

    @measure_execution_time
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert the evaluator instance to a dictionary representation.

        Returns:
            Dict[str, Any]: Dictionary containing all evaluator properties
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "category": self.category.name if self.category else None,
            "type": self.type.name if self.type else None,
            "target_output_key": self.target_output_key,
        }

    def __repr__(self) -> str:
        """String representation of the evaluator."""
        return f"{self.__class__.__name__}(id='{self.id}', name='{self.name}', category={self.category.name})"
