from typing import Any

from uipath.platform.guardrails._evaluators import (
    evaluate_boolean_rule,
    evaluate_number_rule,
    evaluate_universal_rule,
    evaluate_word_rule,
)

from ..._utils import Endpoint, RequestSpec
from ...tracing import traced
from ..common import BaseService, UiPathApiConfig, UiPathExecutionContext
from .guardrails import (
    BooleanRule,
    BuiltInValidatorGuardrail,
    CustomGuardrail,
    Guardrail,
    GuardrailValidationResult,
    NumberRule,
    UniversalRule,
    WordRule,
)


class GuardrailsService(BaseService):
    """Service for validating text against UiPath Guardrails.

    This service provides an interface for evaluating built-in guardrails such as:

    - PII detection
    - Prompt injection detection

    Deterministic and custom guardrails are not yet supported.

    !!! info "Version Availability"
        This service is available starting from **uipath** version **2.2.12**.
    """

    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced("evaluate_guardrail", run_type="uipath")
    def evaluate_guardrail(
        self,
        input_data: str | dict[str, Any],
        guardrail: Guardrail,
    ) -> GuardrailValidationResult:
        """Validate input text using the provided guardrail.

        Args:
            input_data: The text or structured data to validate. Dictionaries will be converted to a string before validation.
            guardrail: A guardrail instance used for validation. Must be an instance of ``BuiltInValidatorGuardrail``. Custom guardrails are not supported.

        Returns:
            BuiltInGuardrailValidationResult: The outcome of the guardrail evaluation, containing whether validation passed and the reason.

        Raises:
            NotImplementedError: If a non-built-in guardrail is provided.
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
        input_data: dict[str, Any],
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
        input_data: dict[str, Any],
        output_data: dict[str, Any],
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
