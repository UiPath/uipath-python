"""Base evaluator abstract class for agent evaluation."""

import functools
import json
import time
import warnings
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Generic, TypeVar, Union, cast, get_args

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


class BaseEvaluatorJustification(BaseModel):
    """Base class for all evaluator justifications."""

    pass


T = TypeVar("T", bound=BaseEvaluationCriteria)
C = TypeVar("C", bound=BaseEvaluatorConfig)
J = TypeVar("J", bound=Union[str, None, BaseEvaluatorJustification])


class BaseEvaluator(BaseModel, Generic[T, C, J], ABC):
    """Abstract base class for all evaluators."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    config: dict[str, Any] = Field(description="The config dictionary")
    config_type: type[C] = Field(description="The config type class")
    evaluation_criteria_type: type[T] = Field(
        description="The type used for evaluation criteria validation and creation"
    )
    justification_type: type[J] = Field(
        description="The type used for justification validation and creation"
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

            # Always extract and set justification_type
            justification_type = cls._extract_justification_type()
            values["justification_type"] = justification_type

            # Validate and create the config object if config dict is provided
            if config_dict := values.get("config"):
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
        if not (
            hasattr(cls, "model_fields")
            and "evaluation_criteria_type" in cls.model_fields
        ):
            raise ValueError(
                f"Could not find evaluation_criteria_type field in {cls.__name__}. "
                f"Ensure the class properly inherits from BaseEvaluator with correct Generic parameters."
            )

        field_info = cls.model_fields["evaluation_criteria_type"]
        if not hasattr(field_info, "annotation"):
            raise ValueError(
                f"No annotation found for evaluation_criteria_type field in {cls.__name__}."
            )

        # Extract the inner type from type[SomeType]
        annotation = field_info.annotation
        args = get_args(annotation)
        if not args:
            raise ValueError(
                f"Invalid annotation for evaluation_criteria_type in {cls.__name__}: {annotation}. "
                f"Expected type[SomeEvaluationCriteria]."
            )

        criteria_type = args[0]
        if not (
            isinstance(criteria_type, type)
            and issubclass(criteria_type, BaseEvaluationCriteria)
        ):
            raise ValueError(
                f"Invalid evaluation criteria type {criteria_type} in {cls.__name__}. "
                f"Must be a subclass of BaseEvaluationCriteria."
            )

        return criteria_type

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

        # Check if Pydantic has already resolved the config_type field annotation
        if not (hasattr(cls, "model_fields") and "config_type" in cls.model_fields):
            raise ValueError(
                f"Could not find config_type field in {cls.__name__}. "
                f"Ensure the class properly inherits from BaseEvaluator with correct Generic parameters."
            )

        field_info = cls.model_fields["config_type"]
        if not hasattr(field_info, "annotation"):
            raise ValueError(
                f"No annotation found for config_type field in {cls.__name__}."
            )

        # Extract the inner type from type[SomeType]
        annotation = field_info.annotation
        args = get_args(annotation)
        if not args:
            raise ValueError(
                f"Invalid annotation for config_type in {cls.__name__}: {annotation}. "
                f"Expected type[SomeEvaluatorConfig]."
            )

        config_type = args[0]
        if not (
            isinstance(config_type, type)
            and issubclass(config_type, BaseEvaluatorConfig)
        ):
            raise ValueError(
                f"Invalid config type {config_type} in {cls.__name__}. "
                f"Must be a subclass of BaseEvaluatorConfig."
            )

        return config_type

    @classmethod
    def _extract_justification_type(cls) -> type[J]:
        """Extract the justification type from Pydantic model fields.

        Returns:
            The justification type (str, None, or BaseEvaluatorJustification subclass)

        Note:
            Unlike the other type extraction methods, this one returns a default (type(None))
            instead of raising an error, since justification support is optional and
            defaults to None for evaluators that don't specify a justification type.
        """
        # Special case: if this is the BaseEvaluator class itself, return type(None)
        if cls.__name__ == "BaseEvaluator":
            return cast(type[J], type(None))

        # Check if Pydantic has resolved the justification_type field annotation
        if not (
            hasattr(cls, "model_fields") and "justification_type" in cls.model_fields
        ):
            # Default to None if field doesn't exist (justification is optional)
            return cast(type[J], type(None))

        field_info = cls.model_fields["justification_type"]
        if not hasattr(field_info, "annotation"):
            # Default to None if no annotation (justification is optional)
            return cast(type[J], type(None))

        # Extract the inner type from type[SomeType]
        annotation = field_info.annotation
        args = get_args(annotation)
        if not args:
            # Default to None if no type args (justification is optional)
            return cast(type[J], type(None))

        justification_type = args[0]

        # Validate the justification type - must be str, type(None), or BaseEvaluatorJustification subclass
        if justification_type is str or justification_type is type(None):
            return cast(type[J], justification_type)
        elif isinstance(justification_type, type) and issubclass(
            justification_type, BaseEvaluatorJustification
        ):
            return cast(type[J], justification_type)
        else:
            # Invalid justification type - log warning but default to None for robustness
            warnings.warn(
                f"Invalid justification type {justification_type} in {cls.__name__}. "
                f"Must be str, None, or subclass of BaseEvaluatorJustification. Defaulting to None.",
                UserWarning,
                stacklevel=2,
            )
            return cast(type[J], type(None))

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
            return criteria
        elif isinstance(criteria, dict):
            return self.evaluation_criteria_type.model_validate(criteria)
        elif hasattr(criteria, "__dict__"):
            # Try to convert from another object type
            return self.evaluation_criteria_type.model_validate(criteria.__dict__)
        else:
            # Try to let Pydantic handle the conversion
            try:
                return self.evaluation_criteria_type.model_validate(criteria)
            except Exception as e:
                raise ValueError(
                    f"Cannot convert {type(criteria)} to {self.evaluation_criteria_type}: {e}"
                ) from e

    def validate_justification(self, justification: Any) -> J:
        """Validate and convert input to the correct justification type.

        Args:
            justification: The justification to validate (str, None, dict, BaseEvaluatorJustification, or other)

        Returns:
            The validated justification of the correct type
        """
        # The key insight: J is constrained to be one of str, None, or BaseEvaluatorJustification
        # At instantiation time, J gets bound to exactly one of these types
        # We need to handle each case and ensure the return matches the bound type

        # Handle None type - when J is bound to None (the literal None type)
        if self.justification_type is type(None):
            # When J is None, we can only return None
            return cast(J, justification if justification is None else None)

        # Handle str type - when J is bound to str
        if self.justification_type is str:
            # When J is str, we must return a str
            if justification is None:
                return cast(J, "")
            return cast(J, str(justification))

        # Handle BaseEvaluatorJustification subclasses - when J is bound to a specific subclass
        if isinstance(self.justification_type, type) and issubclass(
            self.justification_type, BaseEvaluatorJustification
        ):
            # When J is a BaseEvaluatorJustification subclass, we must return that type
            if justification is None:
                raise ValueError(
                    f"None is not allowed for justification type {self.justification_type}"
                )

            if isinstance(justification, self.justification_type):
                return cast(J, justification)
            elif isinstance(justification, dict):
                return cast(J, self.justification_type.model_validate(justification))
            elif hasattr(justification, "__dict__"):
                return cast(
                    J, self.justification_type.model_validate(justification.__dict__)
                )
            else:
                try:
                    return cast(
                        J, self.justification_type.model_validate(justification)
                    )
                except Exception as e:
                    raise ValueError(
                        f"Cannot convert {type(justification)} to {self.justification_type}: {e}"
                    ) from e

        # Fallback: try to return as-is or raise error
        raise ValueError(
            f"Unsupported justification type {self.justification_type} for input {type(justification)}"
        )

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

    async def validate_and_evaluate_criteria(
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
