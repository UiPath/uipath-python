"""Base evaluator abstract class for agent evaluation."""

import functools
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional, TypeVar, Generic

from uipath.eval.models import (
    EvaluationResult,
    EvaluatorCategory,
    EvaluatorType,
)
from uipath.tracing import UiPathEvalSpan


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


T = TypeVar('T')


class BaseEvaluator(Generic[T], ABC):
    """Abstract base class for all evaluators."""

    def __init_subclass__(cls, **kwargs):
        """Enforce that subclasses specify the generic type parameter."""
        super().__init_subclass__(**kwargs)

        # Check if the class properly specifies the generic type
        if not hasattr(cls, '__orig_bases__'):
            raise TypeError(f"{cls.__name__} must specify a generic type parameter (e.g., BaseEvaluator[YourType])")

        # Ensure at least one base is a parameterized generic
        has_generic = any(
            hasattr(base, '__origin__') and hasattr(base, '__args__')
            for base in cls.__orig_bases__
        )

        if not has_generic and cls.__name__ != 'BaseEvaluator':
            raise TypeError(f"{cls.__name__} must inherit from a parameterized BaseEvaluator (e.g., BaseEvaluator[YourType])")

    def __init__(
        self, name: str, description: Optional[str] = None, target_output_key: str = "*"
    ) -> None:
        """Initialize the base evaluator.

        Args:
            name: Display name for the evaluator
            description: Optional description of the evaluator's purpose
            target_output_key: Key to target in output for evaluation ("*" for entire output)
        """
        self.name: str = name
        self.description: Optional[str] = description
        self.target_output_key: str = target_output_key
        self.created_at: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.updated_at: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.category: EvaluatorCategory = EvaluatorCategory.Custom
        self.type: EvaluatorType = EvaluatorType.Custom
        pass

    @classmethod
    def from_params(
        cls,
        category: EvaluatorCategory,
        evaluator_type: EvaluatorType,
        name: str,
        description: str,
        created_at: str,
        updated_at: str,
        target_output_key: str,
        **kwargs: Any,
    ):
        """Initialize the base evaluator from individual parameters.

        Args:
            category: EvaluatorCategory enum value
            evaluator_type: EvaluatorType enum value
            name: Display name of the evaluator
            description: Description of what the evaluator does
            created_at: Creation timestamp
            updated_at: Last update timestamp
            target_output_key: Key to target in output for evaluation
            **kwargs: Additional specific parameters for concrete evaluators

        Returns:
            Initialized evaluator instance
        """
        instance = cls(
            name=name,
            description=description,
            target_output_key=target_output_key,
            **kwargs,
        )
        instance.category = category
        instance.type = evaluator_type
        instance.name = name
        instance.description = description
        instance.created_at = created_at
        instance.updated_at = updated_at
        instance.target_output_key = target_output_key
        return instance

    @measure_execution_time
    @abstractmethod
    async def evaluate(
        self,
        agent_input: Optional[Dict[str, Any]],
        evaluation_criteria: T,
        actual_output: Dict[str, Any],
        execution_logs: str,
        uipath_eval_spans: Optional[list[UiPathEvalSpan]],
    ) -> EvaluationResult:
        """Evaluate the given data and return a result.

        Args:
            agent_input: The input received by the agent
            evaluation_criteria: The criteria to evaluate
            actual_output: The actual output from the agent
            uipath_eval_spans: The execution spans to use for the evaluation
            execution_logs: Execution logs to use for the evaluation

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
        return f"{self.__class__.__name__}(name='{self.name}', category={self.category.name})"
