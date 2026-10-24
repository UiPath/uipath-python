import logging
import re
from typing import Any, Optional

from httpx import HTTPStatusError
from uipath.core.guardrails import (
    GuardrailValidationErrorType,
    GuardrailValidationResult,
    GuardrailValidationResultType,
)
from uipath.core.tracing import traced

from uipath.platform.constants import HEADER_FOLDER_KEY, HEADER_GUARDRAILS_SOURCE

from ..chat.llm_trace_context import build_trace_context_headers
from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig, UiPathConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._job_context import header_job_key
from ..common._models import Endpoint, RequestSpec
from ..errors import EnrichedException
from .guardrails import (
    BYO_VALIDATOR_TYPE,
    BuiltInValidatorGuardrail,
    GuardrailAttachment,
    GuardrailTerminationMode,
)

logger = logging.getLogger(__name__)

_ATTACHMENT_VALIDATE_TIMEOUT_SECONDS = 60.0


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
                logger.warning(
                    "Unknown guardrail validation result '%s'; treating it as %s.",
                    result_str,
                    GuardrailValidationResultType.VALIDATION_FAILED.value,
                )
                return GuardrailValidationResultType.VALIDATION_FAILED

    @staticmethod
    def _parse_error_type(result_str: Any) -> Optional[GuardrailValidationErrorType]:
        """Parse a result string the API returns when it could not validate.

        Args:
            result_str: The result string from the API response (e.g., "PROVIDER_ERROR").

        Returns:
            Optional[GuardrailValidationErrorType]: Why the validation could not
                complete, or None when the result is not an error.
        """
        if not isinstance(result_str, str):
            return None
        try:
            return GuardrailValidationErrorType(result_str.lower())
        except ValueError:
            return None

    @traced("evaluate_guardrail", run_type="uipath")
    def evaluate_guardrail(
        self,
        input_data: str | dict[str, Any],
        guardrail: BuiltInValidatorGuardrail,
        *,
        attachments: list[GuardrailAttachment] | None = None,
        termination_mode: GuardrailTerminationMode | None = None,
    ) -> GuardrailValidationResult:
        """Validate input text using the provided guardrail.

        Args:
            input_data: The text or structured data to validate. Dictionaries will be converted to a string before validation.
            guardrail: A guardrail instance used for validation.
            attachments: Files the guardrail may inspect. ``None`` omits the field, so
                the backend checks only the text. An empty list is sent as ``[]``,
                meaning files apply but there are none to inspect.
            termination_mode: ``FAIL_FAST`` stops scanning at the first violation;
                ``EVALUATE_ALL`` or ``None`` scans everything.

        Returns:
            GuardrailValidationResult: The outcome of the guardrail evaluation.
        """
        parameters = [
            param.model_dump(by_alias=True) for param in guardrail.validator_parameters
        ]
        payload: dict[str, Any] = {
            "validator": guardrail.validator_type,
            "input": input_data if isinstance(input_data, str) else str(input_data),
            "parameters": parameters,
            "guardrailName": guardrail.name,
        }
        if guardrail.validator_type == BYO_VALIDATOR_TYPE:
            if not guardrail.byo_validator_name:
                raise ValueError(
                    "BYO (Bring Your Own) guardrails require byo_validator_name."
                )
            payload["byoValidatorName"] = guardrail.byo_validator_name
        if attachments is not None:
            payload["attachments"] = [a.model_dump(by_alias=True) for a in attachments]
        if termination_mode is not None:
            payload["terminationMode"] = termination_mode.value
        spec = RequestSpec(
            method="POST",
            endpoint=Endpoint("/agentsruntime_/api/execution/guardrails/validate"),
            json=payload,
        )
        # Include trace context headers for server-side span correlation, plus
        # the execution source (x-uipath-guardrails-source) and job key headers
        # for licensing/metering correlation. The execution source is read from
        # the execution context, propagated from the runtime context.
        trace_headers = build_trace_context_headers(extra_baggage=["source=agents"])
        source_headers: dict[str, str] = {}
        execution_source = self._execution_context.execution_source
        if execution_source:
            source_headers[HEADER_GUARDRAILS_SOURCE] = execution_source
        folder_headers: dict[str, str] = {}
        if attachments and UiPathConfig.folder_key:
            folder_headers[HEADER_FOLDER_KEY] = UiPathConfig.folder_key
        request_headers = {
            **(spec.headers or {}),
            **trace_headers,
            **source_headers,
            **header_job_key(),
            **folder_headers,
        }
        request_kwargs: dict[str, Any] = {
            "json": spec.json,
            "headers": request_headers,
        }
        if attachments:
            request_kwargs["timeout"] = _ATTACHMENT_VALIDATE_TIMEOUT_SECONDS

        span_id = None
        try:
            response = self.request(
                spec.method,
                url=spec.endpoint,
                **request_kwargs,
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

        result_str = response_data.get("result", "")
        reason = response_data.get("details", "")

        error_type = self._parse_error_type(result_str)
        if error_type is not None:
            # The service could not evaluate the input: fail closed so the
            # guardrail action still fires, and report why on error_type.
            logger.warning(
                "Guardrail '%s' could not be evaluated (%s): %s",
                guardrail.name,
                result_str,
                reason,
            )
            result = GuardrailValidationResultType.VALIDATION_FAILED
        else:
            result = self._parse_result(result_str)

        # Prepare model data
        model_data: dict[str, Any] = {
            "result": result.value,
            "reason": reason,
        }
        if error_type is not None:
            model_data["errorType"] = error_type.value
        if span_id:
            model_data["spanId"] = span_id
        flagged_attachment_ids = response_data.get("flaggedAttachmentIds")
        if isinstance(flagged_attachment_ids, list):
            model_data["flaggedAttachmentIds"] = [
                str(attachment_id) for attachment_id in flagged_attachment_ids
            ]

        return GuardrailValidationResult.model_validate(model_data)
