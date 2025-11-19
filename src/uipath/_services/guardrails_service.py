from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder
from ..agent.guardrails._evaluators import (
    evaluate_boolean_rule,
    evaluate_number_rule,
    evaluate_universal_rule,
    evaluate_word_rule,
)
from ..models.guardrails import (
    BooleanRule,
    BuiltInValidatorGuardrail,
    CustomGuardrail,
    Guardrail,
    NumberRule,
    UniversalRule,
    WordRule,
)
from ..tracing import traced
from ._base_service import BaseService


class GuardrailValidationResult(BaseModel):
    """Result from guardrail validation."""

    model_config = ConfigDict(populate_by_name=True)

    validation_passed: bool = Field(alias="validation_passed")
    reason: str = Field(alias="reason")


class GuardrailViolationError(Exception):
    """Exception raised when guardrail validation fails."""

    def __init__(self, detected_issue: Any):
        self.detected_issue = detected_issue
        super().__init__(f"Guardrail violation detected: {detected_issue}")


class GuardrailsService(FolderContext, BaseService):
    """Service for validating text against UiPath Guardrails."""

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced("evaluate_guardrail", run_type="uipath")
    def evaluate_guardrail(
        self,
        input_data: Union[str, Dict[str, Any]],
        guardrail: Guardrail,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> GuardrailValidationResult:
        """Call the API to validate input_data with the given guardrail.

        Only supports built-in guardrails for now.
        """
        if isinstance(guardrail, BuiltInValidatorGuardrail):
            parameters = [
                param.model_dump(by_alias=True)
                for param in guardrail.validator_parameters
            ]
            payload = {
                "validator": guardrail.validator_type,
                "input": input_data if isinstance(input_data, str) else str(input_data),
                "parameters": parameters,
            }
            spec = RequestSpec(
                method="POST",
                endpoint=Endpoint("/agentsruntime_/api/execution/guardrails/validate"),
                json=payload,
                headers={**header_folder(folder_key, folder_path)},
            )
            response = self.request(
                spec.method,
                url=spec.endpoint,
                json=spec.json,
                headers=spec.headers,
            )
            return GuardrailValidationResult.model_validate(response.json())
        else:
            raise NotImplementedError(
                "Custom guardrail validation is not yet supported by the API."
            )

    @traced("evaluate_pre_custom_guardrails", run_type="uipath")
    def evaluate_pre_custom_guardrails(
        self,
        input_data: Dict[str, Any],
        guardrail: CustomGuardrail,
    ) -> GuardrailValidationResult:
        """Evaluate custom guardrail rules against input data (pre-execution)."""
        return self.evaluate_post_custom_guardrails(
            input_data=input_data,
            output_data={},
            guardrail=guardrail,
        )

    @traced("evaluate_post_custom_guardrails", run_type="uipath")
    def evaluate_post_custom_guardrails(
        self,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        guardrail: CustomGuardrail,
    ) -> GuardrailValidationResult:
        """Evaluate custom guardrail rules against input and output data."""
        for rule in guardrail.rules:
            if isinstance(rule, WordRule):
                passed, reason = evaluate_word_rule(rule, input_data, output_data)
            elif isinstance(rule, NumberRule):
                passed, reason = evaluate_number_rule(rule, input_data, output_data)
            elif isinstance(rule, BooleanRule):
                passed, reason = evaluate_boolean_rule(rule, input_data, output_data)
            elif isinstance(rule, UniversalRule):
                passed, reason = evaluate_universal_rule(rule, output_data)
            else:
                return GuardrailValidationResult(
                    validation_passed=False,
                    reason=f"Unknown rule type: {type(rule)}",
                )

            if not passed:
                return GuardrailValidationResult(
                    validation_passed=False, reason=reason or "Rule validation failed"
                )

        return GuardrailValidationResult(
            validation_passed=True, reason="All custom guardrail rules passed"
        )
