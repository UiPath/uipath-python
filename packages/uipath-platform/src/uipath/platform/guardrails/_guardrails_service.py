import re
from typing import Any, Optional

from httpx import HTTPStatusError
from uipath.core.guardrails import (
    GuardrailValidationResult,
    GuardrailValidationResultType,
)
from uipath.core.tracing import traced

from ..chat.llm_trace_context import build_trace_context_headers
from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._job_context import header_job_key
from ..common._models import Endpoint, RequestSpec
from ..common.constants import HEADER_GUARDRAILS_SOURCE
from ..errors import EnrichedException
from .guardrails import BuiltInValidatorGuardrail

# x-uipath-traceparent-id header format: {version}-{trace_id}-{span_id}[-{trace_flags}]
# Based on W3C traceparent but allows 16- or 32-hex span IDs.
_TRACEPARENT_PATTERN = re.compile(
    r"^[0-9a-f]{2}-[0-9a-f]{32}-(?P<span_id>[0-9a-f]{16}|[0-9a-f]{32})(?:-[0-9a-f]{2})?$",
    re.IGNORECASE,
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

    @staticmethod
    def _extract_span_id_from_traceparent(
        traceparent: Optional[str],
    ) -> Optional[str]:
        """Extract span ID from x-uipath-traceparent-id header and format as GUID.

        Args:
            traceparent: Value from the ``x-uipath-traceparent-id`` response header.
                Accepts 3-part ``"00-{trace_id}-{span_id}"`` or 4-part
                ``"00-{trace_id}-{span_id}-{trace_flags}"``. Span ID may be
                16 or 32 hex chars.

        Returns:
            Span ID formatted as lowercase GUID (8-4-4-4-12), or None if not parseable.
        """
        if not traceparent:
            return None
        match = _TRACEPARENT_PATTERN.match(traceparent)
        if not match:
            return None
        span_id_hex = match.group("span_id").lower()
        # Pad to 32 chars for GUID conversion (span IDs may be 16 hex chars)
        padded = span_id_hex.zfill(32)
        return f"{padded[:8]}-{padded[8:12]}-{padded[12:16]}-{padded[16:20]}-{padded[20:32]}"

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
            "guardrailName": guardrail.name,
        }
        spec = RequestSpec(
            method="POST",
            endpoint=Endpoint("/agentsruntime_/api/execution/guardrails/validate"),
            json=payload,
        )
        # Include trace context headers for server-side span correlation, plus
        # the execution source (x-uipath-guardrails-source) and job key headers
        # for licensing/metering correlation. The execution source is read from
        # the execution context, propagated from the runtime context.
        trace_headers = build_trace_context_headers()
        source_headers: dict[str, str] = {}
        execution_source = self._execution_context.execution_source
        if execution_source:
            source_headers[HEADER_GUARDRAILS_SOURCE] = execution_source
        request_headers = {
            **(spec.headers or {}),
            **trace_headers,
            **source_headers,
            **header_job_key(),
        }
        span_id = None
        try:
            response = self.request(
                spec.method,
                url=spec.endpoint,
                json=spec.json,
                headers=request_headers,
            )
            span_id = self._extract_span_id_from_traceparent(
                response.headers.get("x-uipath-traceparent-id")
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
                        span_id = self._extract_span_id_from_traceparent(
                            original_error.response.headers.get(
                                "x-uipath-traceparent-id"
                            )
                        )
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
        model_data: dict[str, Any] = {
            "result": result.value,
            "reason": reason,
        }
        if span_id:
            model_data["spanId"] = span_id

        return GuardrailValidationResult.model_validate(model_data)
