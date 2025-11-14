"""Base evaluator abstract class for agent evaluation."""

import json
import warnings
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, Union, cast, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from .._helpers.helpers import track_evaluation_metrics
from ..models import AgentExecution, EvaluationResult
from ..models.models import UiPathEvaluationError, UiPathEvaluationErrorCategory


class BaseEvaluationCriteria(BaseModel):
    """Base class for all evaluation criteria."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    pass


# Type variable for evaluation criteria, used by both Config and Evaluator
T = TypeVar("T", bound=BaseEvaluationCriteria)


class BaseEvaluatorConfig(BaseModel, Generic[T]):
    """Base class for all evaluator configurations.

    Generic over T (evaluation criteria type) to ensure type safety between
    the config's default_evaluation_criteria and the evaluator's expected criteria type.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str = Field(description="The name of the evaluator")
    description: str = Field(default="", description="The description of the evaluator")
    default_evaluation_criteria: T | None = None


class BaseEvaluatorJustification(BaseModel):
    """Base class for all evaluator justifications."""

    pass


# Additional type variables for Config and Justification
# Note: C must be BaseEvaluatorConfig[T] to ensure type consistency
C = TypeVar("C", bound=BaseEvaluatorConfig[Any])
J = TypeVar("J", bound=Union[str, None, BaseEvaluatorJustification])


class BaseEvaluator(BaseModel, Generic[T, C, J], ABC):
    """Abstract base class for all evaluators.

    Generic Parameters:
        T: The evaluation criteria type (bound to BaseEvaluationCriteria)
        C: The evaluator config type (bound to BaseEvaluatorConfig[T])
        J: The justification type (str, None, or BaseEvaluatorJustification subclass)

    Design Rationale:
        T is explicitly specified even though C = BaseEvaluatorConfig[T] already encodes it.
        This redundancy is intentional and provides:

        1. **Type Checker Support**: Static type checkers can infer the exact criteria type
           for the evaluate() method signature without runtime introspection

        2. **Clear API**: The signature BaseEvaluator[MyCriteria, MyConfig[MyCriteria], str]
           makes it immediately obvious what criteria type is expected

        3. **IDE Support**: Autocomplete and type hints work perfectly for method parameters

        Runtime validation ensures T and C's generic parameter are consistent.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
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

    @property
    def name(self) -> str:
        """Evaluator's name."""
        return self.evaluator_config.name

    @name.setter
    def name(self, value: str) -> None:
        """Set the evaluator's name."""
        self.evaluator_config.name = value

    @property
    def description(self) -> str:
        """Evaluator's description."""
        return self.evaluator_config.description

    @description.setter
    def description(self, value: str) -> None:
        """Set the evaluator's description."""
        self.evaluator_config.description = value

    @model_validator(mode="before")
    @classmethod
    def validate_model(cls, values: Any) -> Any:
        """Pre-initialization model validator for Pydantic models.

        This validator extracts the Generic type parameters and validates their consistency.

        Args:
            values: The raw input values before validation

        Returns:
            The validated/transformed values with types set

        Raises:
            ValueError: If types cannot be determined or are inconsistent
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

            # Validate consistency: config's generic parameter should match criteria_type
            cls._validate_type_consistency(config_type, criteria_type)

            # Validate and create the config object if config dict is provided
            try:
                validated_config = config_type.model_validate(values.get("config", {}))
                values["evaluator_config"] = validated_config
            except Exception as e:
                raise UiPathEvaluationError(
                    code="FAILED_TO_VALIDATE_EVALUATOR_CONFIG",
                    title=f"Failed to validate evaluator config for {cls.__name__}",
                    detail=f"Error: {e}",
                    category=UiPathEvaluationErrorCategory.SYSTEM,
                ) from e

        return values

    @classmethod
    def _validate_type_consistency(
        cls,
        config_type: type[BaseEvaluatorConfig[Any]],
        criteria_type: type[BaseEvaluationCriteria],
    ) -> None:
        """Validate that the config's generic parameter matches the evaluator's criteria type.

        Extracts the criteria type from the config's default_evaluation_criteria field
        annotation and validates it matches the evaluator's expected criteria type.

        Args:
            config_type: The config type to validate
            criteria_type: The expected evaluation criteria type

        Raises:
            ValueError: If the types are inconsistent
        """
        # Skip validation for base classes
        if config_type.__name__ in (
            "BaseEvaluatorConfig",
            "OutputEvaluatorConfig",
            "BaseLLMJudgeEvaluatorConfig",
        ):
            return

        # Extract from Pydantic's model_fields which preserves generic types
        if (
            hasattr(config_type, "model_fields")
            and "default_evaluation_criteria" in config_type.model_fields
        ):
            field_info = config_type.model_fields["default_evaluation_criteria"]
            if hasattr(field_info, "annotation"):
                annotation = field_info.annotation
                # The annotation will be SomeCriteria | None
                args = get_args(annotation)
                if args:
                    # Get the criteria type (the non-None arg)
                    for arg in args:
                        if (
                            arg is not type(None)
                            and isinstance(arg, type)
                            and issubclass(arg, BaseEvaluationCriteria)
                        ):
                            # Found the config's criteria type, check if it matches
                            if arg != criteria_type:
                                raise UiPathEvaluationError(
                                    code="TYPE_INCONSISTENCY_IN_EVALUATOR",
                                    title=f"Type inconsistency in {cls.__name__}: "
                                    f"Config {config_type.__name__} expects criteria type {arg.__name__}",
                                    detail=f"Evaluator expects {criteria_type.__name__}. "
                                    f"Ensure BaseEvaluator[T, C[T], J] has matching T and C[T] parameters.",
                                    category=UiPathEvaluationErrorCategory.SYSTEM,
                                )
                            return  # Validation passed

    @classmethod
    def _extract_evaluation_criteria_type(cls) -> type[BaseEvaluationCriteria]:
        """Extract the evaluation criteria type from Pydantic model fields.

        Returns:
            The evaluation criteria type

        Raises:
            ValueError: If no valid evaluation criteria type can be determined from the class definition
        """
        # Special case: if this is the BaseEvaluator class itself, return BaseEvaluationCriteria
        if cls.__name__ == ("BaseEvaluator" or "BaseEvaluator[Any, Any, Any]"):
            return BaseEvaluationCriteria

        # Check if Pydantic has already resolved the evaluation_criteria_type field annotation
        if not (
            hasattr(cls, "model_fields")
            and "evaluation_criteria_type" in cls.model_fields
        ):
            raise UiPathEvaluationError(
                code="COULD_NOT_FIND_EVALUATION_CRITERIA_TYPE_FIELD",
                title=f"Could not find evaluation_criteria_type field in {cls.__name__}",
                detail="Ensure the class properly inherits from BaseEvaluator with correct Generic parameters.",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            )

        field_info = cls.model_fields["evaluation_criteria_type"]
        if not hasattr(field_info, "annotation"):
            raise UiPathEvaluationError(
                code="NO_ANNOTATION_FOUND_FOR_EVALUATION_CRITERIA_TYPE_FIELD",
                title=f"No annotation found for evaluation_criteria_type field in {cls.__name__}",
                detail="Ensure the class properly inherits from BaseEvaluator with correct Generic parameters.",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            )

        # Extract the inner type from type[SomeType]
        annotation = field_info.annotation
        args = get_args(annotation)
        if not args:
            raise UiPathEvaluationError(
                code="INVALID_ANNOTATION_FOR_EVALUATION_CRITERIA_TYPE",
                title=f"Invalid annotation for evaluation_criteria_type in {cls.__name__}: {annotation}",
                detail="Expected type[SomeEvaluationCriteria]",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            )

        criteria_type = args[0]
        if not (
            isinstance(criteria_type, type)
            and issubclass(criteria_type, BaseEvaluationCriteria)
        ):
            raise UiPathEvaluationError(
                code="INVALID_EVALUATION_CRITERIA_TYPE",
                title=f"Invalid evaluation criteria type {criteria_type} in {cls.__name__}",
                detail=f"{criteria_type} must be a subclass of BaseEvaluationCriteria",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            )

        return criteria_type

    @classmethod
    def _extract_config_type(cls) -> type[BaseEvaluatorConfig[Any]]:
        """Extract the config type from Pydantic model fields.

        Returns:
            The config type for this evaluator

        Raises:
            ValueError: If no valid config type can be determined from the class definition
        """
        # Special case: if this is the BaseEvaluator class itself, return BaseEvaluatorConfig
        if cls.__name__ == ("BaseEvaluator" or "BaseEvaluator[Any, Any, Any]"):
            return BaseEvaluatorConfig
        # Check if Pydantic has already resolved the config_type field annotation
        if not (hasattr(cls, "model_fields") and "config_type" in cls.model_fields):
            raise UiPathEvaluationError(
                code="COULD_NOT_FIND_CONFIG_TYPE_FIELD",
                title=f"Could not find config_type field in {cls.__name__}",
                detail="Ensure the class properly inherits from BaseEvaluator with correct Generic parameters.",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            )

        field_info = cls.model_fields["config_type"]
        if not hasattr(field_info, "annotation"):
            raise UiPathEvaluationError(
                code="NO_ANNOTATION_FOUND_FOR_CONFIG_TYPE_FIELD",
                title=f"No annotation found for config_type field in {cls.__name__}",
                detail="Ensure the class properly inherits from BaseEvaluator with correct Generic parameters.",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            )

        # Extract the inner type from type[SomeType]
        annotation = field_info.annotation
        args = get_args(annotation)
        if not args:
            raise UiPathEvaluationError(
                code="INVALID_ANNOTATION_FOR_CONFIG_TYPE",
                title=f"Invalid annotation for config_type in {cls.__name__}: {annotation}",
                detail="Expected type[SomeEvaluatorConfig]",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            )

        config_type = args[0]
        if not (
            isinstance(config_type, type)
            and issubclass(config_type, BaseEvaluatorConfig)
        ):
            raise UiPathEvaluationError(
                code="INVALID_CONFIG_TYPE",
                title=f"Invalid config type {config_type} in {cls.__name__}",
                detail=f"{config_type} must be a subclass of BaseEvaluatorConfig",
                category=UiPathEvaluationErrorCategory.SYSTEM,
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
        try:
            # Special case: if this is the BaseEvaluator class itself, return type(None)
            if cls.__name__ == "BaseEvaluator[Any, Any, Any]":
                return cast(type[J], type(None))

            # Check if Pydantic has resolved the justification_type field annotation
            if not (
                hasattr(cls, "model_fields")
                and "justification_type" in cls.model_fields
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
        except Exception as e:
            raise UiPathEvaluationError(
                code="CANNOT_EXTRACT_JUSTIFICATION_TYPE",
                title=f"Cannot extract justification type from {cls.__name__}",
                detail=f"Error: {e}",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            ) from e

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
        try:
            if isinstance(criteria, self.evaluation_criteria_type):
                return criteria
            elif isinstance(criteria, dict):
                return self.evaluation_criteria_type.model_validate(criteria)
            elif hasattr(criteria, "__dict__"):
                # Try to convert from another object type
                return self.evaluation_criteria_type.model_validate(criteria.__dict__)
            else:
                # Try to let Pydantic handle the conversion
                return self.evaluation_criteria_type.model_validate(criteria)
        except Exception as e:
            raise UiPathEvaluationError(
                code="CANNOT_VALIDATE_EVALUATION_CRITERIA",
                title=f"Cannot validate {type(criteria)} to {self.evaluation_criteria_type}",
                detail=f"Error: {e}",
                category=UiPathEvaluationErrorCategory.SYSTEM,
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
        try:
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
                    return justification
                elif isinstance(justification, dict):
                    return self.justification_type.model_validate(justification)
                elif hasattr(justification, "__dict__"):
                    return self.justification_type.model_validate(
                        justification.__dict__
                    )
                else:
                    return self.justification_type.model_validate(justification)
        except Exception as e:
            raise UiPathEvaluationError(
                code="CANNOT_CONVERT_JUSTIFICATION",
                title=f"Cannot convert {type(justification)} to {self.justification_type}",
                detail=f"Error: {e}",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            ) from e

        # Fallback: this should never happen
        raise UiPathEvaluationError(
            code="UNSUPPORTED_JUSTIFICATION_TYPE",
            title=f"Unsupported justification type {self.justification_type} for input {type(justification)}",
            detail=f"Unsupported justification type {self.justification_type} for input {type(justification)}",
            category=UiPathEvaluationErrorCategory.SYSTEM,
        )

    @classmethod
    def get_evaluation_criteria_schema(cls) -> dict[str, Any]:
        """Get the JSON schema for the evaluation criteria type.

        Returns:
            The JSON schema for the evaluation criteria type
        """
        criteria_type = cls._extract_evaluation_criteria_type()
        return criteria_type.model_json_schema(by_alias=False)

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        """Get the JSON schema for the config type.

        Returns:
            The JSON schema for the config type
        """
        config_type = cls._extract_config_type()
        return config_type.model_json_schema(by_alias=False)

    @classmethod
    def get_justification_schema(cls) -> dict[str, Any]:
        """Get the JSON schema for the justification type.

        Returns:
            The JSON schema for the justification type
        """
        justification_type = cls._extract_justification_type()
        if justification_type is type(None):
            return {}
        elif justification_type is str:
            return {"type": "string"}
        elif isinstance(justification_type, type) and issubclass(
            justification_type, BaseEvaluatorJustification
        ):
            return justification_type.model_json_schema(by_alias=False)
        else:
            raise UiPathEvaluationError(
                code="INVALID_JUSTIFICATION_TYPE",
                title=f"Invalid justification type {justification_type} in {cls.__name__}",
                detail="Must be str, None, or subclass of BaseEvaluatorJustification",
                category=UiPathEvaluationErrorCategory.SYSTEM,
            )

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

    @classmethod
    @abstractmethod
    def get_evaluator_id(cls) -> str:
        """Get the evaluator id."""
        pass

    @classmethod
    def generate_json_type(cls) -> dict[str, Any]:
        """Generate the JSON schema for the evaluator."""
        return {
            "evaluatorTypeId": cls.get_evaluator_id(),
            "evaluatorConfigSchema": cls.get_config_schema(),
            "evaluationCriteriaSchema": cls.get_evaluation_criteria_schema(),
            "justificationSchema": cls.get_justification_schema(),
        }

    async def validate_and_evaluate_criteria(
        self, agent_execution: AgentExecution, evaluation_criteria: Any
    ) -> EvaluationResult:
        """Evaluate the given data and return a result from a raw evaluation criteria."""
        if evaluation_criteria is None:
            evaluation_criteria = self.evaluator_config.default_evaluation_criteria
        if evaluation_criteria is None:
            raise UiPathEvaluationError(
                code="NO_EVALUATION_CRITERIA_PROVIDED",
                title="No evaluation criteria provided and no default evaluation criteria configured",
                detail="No evaluation criteria provided and no default evaluation criteria configured",
                category=UiPathEvaluationErrorCategory.SYSTEM,
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
