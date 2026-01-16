from typing import Any

from httpx import HTTPStatusError
from uipath.core.guardrails import (
    GuardrailValidationResult,
    GuardrailValidationResultType,
)

from ..._utils import Endpoint, RequestSpec
from ...tracing import traced
from ..common import BaseService, UiPathApiConfig, UiPathExecutionContext
from ..errors import EnrichedException
from .guardrails import BuiltInValidatorGuardrail


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

    @staticmethod
    def _parse_result(result_str: str) -> GuardrailValidationResultType:
        """Parse result string from API response to GuardrailValidationResultType.

        Args:
            result_str: The result string from the API response (e.g., "VALIDATION_FAILED").

        Returns:
            GuardrailValidationResultType: The parsed validation result type.
        """
        if not result_str:
            return GuardrailValidationResultType.VALIDATION_FAILED

        # Convert uppercase enum name to enum value
        # API: "VALIDATION_FAILED" -> enum: "validation_failed"
        result_value = result_str.lower()
        try:
            return GuardrailValidationResultType(result_value)
        except ValueError:
            # If direct conversion fails, try by enum name
            try:
                return GuardrailValidationResultType[result_str]
            except KeyError:
                # Fallback to validation_failed if unknown
                return GuardrailValidationResultType.VALIDATION_FAILED

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
        try:
            response = self.request(
                spec.method,
                url=spec.endpoint,
                json=spec.json,
                headers=spec.headers,
            )
            response_data = response.json()
        except EnrichedException as e:
            # Handle 403 responses: API returns 403 with valid JSON body for
            # ENTITLEMENTS_MISSING or FEATURE_DISABLED cases
            if e.status_code == 403:
                # Access the original HTTPStatusError to get the full response
                original_error = e.__cause__
                if (
                    isinstance(original_error, HTTPStatusError)
                    and original_error.response
                ):
                    try:
                        response_data = original_error.response.json()
                    except Exception:
                        # If JSON parsing fails, re-raise the original exception
                        raise
                else:
                    # Try to parse from response_content if available
                    try:
                        import json

                        response_data = json.loads(e.response_content)
                    except Exception:
                        raise
            else:
                raise

        result = self._parse_result(response_data.get("result", ""))

        reason = response_data.get("details", "")

        # Prepare model data
        model_data = {
            "result": result.value,
            "reason": reason,
        }

        return GuardrailValidationResult.model_validate(model_data)
