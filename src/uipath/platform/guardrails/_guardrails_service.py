from typing import Any

from uipath.core.guardrails import GuardrailValidationResult

from ..._utils import Endpoint, RequestSpec
from ...tracing import traced
from ..common import BaseService, UiPathApiConfig, UiPathExecutionContext
from .guardrails import BuiltInValidatorGuardrail, GuardrailValidationResultType


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
        guardrail: BuiltInValidatorGuardrail,
    ) -> GuardrailValidationResult:
        """Validate input text using the provided guardrail.

        Args:
            input_data: The text or structured data to validate. Dictionaries will be converted to a string before validation.
            guardrail: A guardrail instance used for validation.

        Returns:
            GuardrailValidationResult: The outcome of the guardrail evaluation.
        """
        parameters = [
            param.model_dump(by_alias=True) for param in guardrail.validator_parameters
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
        response_data = response.json()

        # Map API response to populate result enum and details field
        # Handle skip case for entitlements checks
        skip = response_data.get("skip", False)
        validation_passed = response_data.get("validation_passed", False)
        reason = response_data.get("reason", "")

        # Determine result enum value based on skip and validation_passed
        if skip:
            result = GuardrailValidationResultType.SKIPPED
        elif validation_passed:
            result = GuardrailValidationResultType.PASSED
        else:
            result = GuardrailValidationResultType.FAILED

        # Add result and details to response data
        # Convert enum to string value for JSON serialization
        response_data["result"] = result.value
        response_data["details"] = reason

        return GuardrailValidationResult.model_validate(response_data)
