"""Base evaluator abstract class for agent evaluation."""

import functools
import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Generic, TypeVar, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..models import AgentExecution, ErrorEvaluationResult, EvaluationResult


def track_evaluation_metrics(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to track evaluation metrics and handle errors gracefully."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> EvaluationResult:
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
        except Exception as e:
            result = ErrorEvaluationResult(
                details="Exception thrown by evaluator: {}".format(e),
                evaluation_time=time.time() - start_time,
            )
        end_time = time.time()
        execution_time = end_time - start_time

        result.evaluation_time = execution_time
        return result

    return wrapper


class BaseEvaluationCriteria(BaseModel):
    """Base class for all evaluation criteria."""

    pass


class BaseEvaluatorConfig(BaseModel):
    """Base class for all evaluator configurations."""

    name: str
    default_evaluation_criteria: BaseEvaluationCriteria | None = None


T = TypeVar("T", bound=BaseEvaluationCriteria)
C = TypeVar("C", bound=BaseEvaluatorConfig)


class BaseEvaluator(BaseModel, Generic[T, C], ABC):
    """Abstract base class for all evaluators."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    config: dict[str, Any]
    config_type: type[C] = Field(description="The config type class")
    evaluation_criteria_type: type[T] = Field(
        description="The type used for evaluation criteria validation and creation"
    )
    evaluator_config: C = Field(
        exclude=True, description="The validated config object instance"
    )

    def __init_subclass__(cls, **kwargs: Any):
        """Hook for subclass creation - automatically applies evaluation metrics tracking."""
        super().__init_subclass__(**kwargs)

        if hasattr(cls, "evaluate") and not getattr(
            cls.evaluate, "_has_metrics_decorator", False
        ):
            cls.evaluate = track_evaluation_metrics(cls.evaluate)  # type: ignore[method-assign]
            cls.evaluate._has_metrics_decorator = True  # type: ignore[attr-defined]

    @model_validator(mode="before")
    @classmethod
    def validate_model(cls, values: Any) -> Any:
        """Pre-initialization model validator for Pydantic models.

        This validator extracts the Generic type parameter T and sets it as the
        evaluation_criteria_type if not explicitly provided.

        Args:
            values: The raw input values before validation

        Returns:
            The validated/transformed values with evaluation_criteria_type set

        Raises:
            ValueError: If no valid evaluation criteria type can be determined
        """
        if isinstance(values, dict):
            # Always extract and set evaluation_criteria_type
            criteria_type = cls._extract_evaluation_criteria_type()
            values["evaluation_criteria_type"] = criteria_type

            # Always extract and set config_type
            config_type = cls._extract_config_type()
            values["config_type"] = config_type

            # Validate and create the config object if config dict is provided
            if "config" in values:
                config_dict = values["config"]
                try:
                    validated_config = config_type.model_validate(config_dict)
                    values["evaluator_config"] = validated_config
                except Exception as e:
                    raise ValueError(
                        f"Failed to validate config for {cls.__name__}: {e}"
                    ) from e

        return values

    @classmethod
    def _extract_evaluation_criteria_type(cls) -> type[BaseEvaluationCriteria]:
        """Extract the evaluation criteria type from Pydantic model fields.

        Returns:
            The evaluation criteria type

        Raises:
            ValueError: If no valid evaluation criteria type can be determined from the class definition
        """
        # Special case: if this is the BaseEvaluator class itself, return BaseEvaluationCriteria
        if cls.__name__ == "BaseEvaluator":
            return BaseEvaluationCriteria

        # Check if Pydantic has already resolved the evaluation_criteria_type field annotation
        if (
            hasattr(cls, "model_fields")
            and "evaluation_criteria_type" in cls.model_fields
        ):
            field_info = cls.model_fields["evaluation_criteria_type"]
            if hasattr(field_info, "annotation"):
                # Extract the inner type from type[SomeType]
                annotation = field_info.annotation
                args = get_args(annotation)
                if args and len(args) > 0:
                    criteria_type = args[0]
                    if isinstance(criteria_type, type) and issubclass(
                        criteria_type, BaseEvaluationCriteria
                    ):
                        return criteria_type

        # If we reach here, no valid type could be determined
        raise ValueError(
            f"Could not determine evaluation criteria type for {cls.__name__}. "
            f"Ensure the class properly inherits from BaseEvaluator or OutputEvaluator with correct Generic parameters."
        )

    @classmethod
    def _extract_config_type(cls) -> type[BaseEvaluatorConfig]:
        """Extract the config type from Pydantic model fields.

        Returns:
            The config type for this evaluator

        Raises:
            ValueError: If no valid config type can be determined from the class definition
        """
        # Special case: if this is the BaseEvaluator class itself, return BaseEvaluatorConfig
        if cls.__name__ == "BaseEvaluator":
            return BaseEvaluatorConfig

        # Check if Pydantic has already resolved the evaluator_config field annotation
        if hasattr(cls, "model_fields") and "evaluator_config" in cls.model_fields:
            field_info = cls.model_fields["evaluator_config"]
            if hasattr(field_info, "annotation"):
                config_type = field_info.annotation
                if isinstance(config_type, type) and issubclass(
                    config_type, BaseEvaluatorConfig
                ):
                    return config_type

        # Fallback: Look for config_type class attribute
        if hasattr(cls, "config_type") and cls.config_type is not None:
            if isinstance(cls.config_type, type) and issubclass(
                cls.config_type, BaseEvaluatorConfig
            ):
                return cls.config_type
            else:
                raise ValueError(
                    f"config_type {cls.config_type} in {cls.__name__} must be a subclass of BaseEvaluatorConfig"
                )

        # If no config_type found, use the default
        return BaseEvaluatorConfig

    def validate_evaluation_criteria(self, criteria: Any) -> T:
        """Validate and convert input to the correct evaluation criteria type.

        Uses Pydantic's model_validate for proper validation, type coercion,
        and error handling.

        Args:
            criteria: The criteria to validate (dict, BaseEvaluationCriteria, or other)

        Returns:
            An instance of the evaluation criteria type (T)

        Raises:
            ValueError: If the criteria cannot be converted to the expected type
        """
        if isinstance(criteria, self.evaluation_criteria_type):
            return criteria  # type: ignore[return-value]
        elif isinstance(criteria, dict):
            return self.evaluation_criteria_type.model_validate(criteria)  # type: ignore[return-value]
        elif hasattr(criteria, "__dict__"):
            # Try to convert from another object type
            return self.evaluation_criteria_type.model_validate(criteria.__dict__)  # type: ignore[return-value]
        else:
            # Try to let Pydantic handle the conversion
            try:
                return self.evaluation_criteria_type.model_validate(criteria)  # type: ignore[return-value]
            except Exception as e:
                raise ValueError(
                    f"Cannot convert {type(criteria)} to {self.evaluation_criteria_type}: {e}"
                ) from e

    @classmethod
    def get_evaluation_criteria_schema(cls) -> dict[str, Any]:
        """Get the JSON schema for the evaluation criteria type.

        Returns:
            The JSON schema for the evaluation criteria type
        """
        criteria_type = cls._extract_evaluation_criteria_type()
        return criteria_type.model_json_schema()

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        """Get the JSON schema for the config type.

        Returns:
            The JSON schema for the config type
        """
        config_type = cls._extract_config_type()
        return config_type.model_json_schema()

    def _canonical_json(self, obj: Any) -> str:
        """Convert an object to canonical JSON string for consistent comparison.

        Args:
            obj: The object to convert to canonical JSON

        Returns:
            str: Canonical JSON string with normalized numbers and sorted keys
        """
        return json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    async def evaluate_from_raw_criteria(
        self, agent_execution: AgentExecution, evaluation_criteria: Any
    ) -> EvaluationResult:
        """Evaluate the given data and return a result from a raw evaluation criteria."""
        if evaluation_criteria is None:
            evaluation_criteria = self.evaluator_config.default_evaluation_criteria
        if evaluation_criteria is None:
            raise ValueError(
                "No evaluation criteria provided and no default evaluation criteria configured"
            )
        criteria = self.validate_evaluation_criteria(evaluation_criteria)
        return await self.evaluate(agent_execution, criteria)

    @abstractmethod
    async def evaluate(
        self, agent_execution: AgentExecution, evaluation_criteria: T
    ) -> EvaluationResult:
        """Evaluate the given data and return a result.

        Args:
            agent_execution: The execution details containing:
                - agent_input: The input received by the agent
                - agent_output: The actual output from the agent
                - agent_trace: The execution trace from the agent
                - simulation_instructions: The simulation instructions for the agent
            evaluation_criteria: The criteria to evaluate

        Returns:
            EvaluationResult containing the score and details
        """
        pass
