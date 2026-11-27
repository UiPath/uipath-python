import json
import logging
import re
from typing import Any, Optional

from httpx import HTTPStatusError, ReadTimeout, Timeout
from tenacity import retry_if_exception, retry_if_result
from uipath.core.guardrails import (
    GuardrailScope,
    GuardrailValidationErrorType,
    GuardrailValidationResult,
    GuardrailValidationResultType,
)
from uipath.core.tracing import traced

from uipath.platform.constants import (
    HEADER_FOLDER_KEY,
    HEADER_GUARDRAILS_SOURCE,
    HEADER_GUARDRAILS_TIMEOUT_MS,
)

from ..chat.llm_trace_context import build_trace_context_headers
from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig, UiPathConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._job_context import header_job_key
from ..common._models import Endpoint, RequestSpec
from ..common.retry import is_retryable_response, is_retryable_unless_read_timeout
from ..errors import EnrichedException, GuardrailValidationTimeoutError
from .guardrails import (
    BYO_VALIDATOR_TYPE,
    BuiltInValidatorGuardrail,
    GuardrailAttachment,
    GuardrailTerminationMode,
)

logger = logging.getLogger(__name__)

# A validation can outlast the client's default 30 s while a provider is throttled.
# The service is told the same wait, so it stops working when the client stops
# waiting. Connecting keeps the default.
_VALIDATE_RESPONSE_TIMEOUT_SECONDS = 150.0
_VALIDATE_TIMEOUT = Timeout(30.0, read=_VALIDATE_RESPONSE_TIMEOUT_SECONDS)

# The retries of ``BaseService.request``, minus the one after a read timeout: the
# service has the request, and sending it again starts the validation over.
_request_without_read_timeout_retry = BaseService.request.retry_with(  # type: ignore[attr-defined]
    retry=(
        retry_if_exception(is_retryable_unless_read_timeout)
        | retry_if_result(is_retryable_response)
    )
)


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

    def evaluate_guardrail(
        self,
        input_data: str | dict[str, Any],
        guardrail: BuiltInValidatorGuardrail,
        *,
        attachments: list[GuardrailAttachment] | None = None,
        termination_mode: GuardrailTerminationMode | None = None,
        scope: GuardrailScope | None = None,
        execution_stage: str | None = None,
        action_type: str | None = None,
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
            scope: What the check guards: the agent, an LLM call or a tool call.
                Only recorded on the evaluation span; ``None`` omits it.
            execution_stage: ``preExecution`` or ``postExecution``: whether the
                check runs before or after what it guards.
            action_type: What the caller does when the check fails: ``Block``,
                ``Filter``, ``Log`` or ``Escalate``.

        Returns:
            GuardrailValidationResult: The outcome of the guardrail evaluation.

        Raises:
            GuardrailValidationTimeoutError: The service did not answer in time.
                The request is not sent again.
        """
        # In a job, the Guardrails Service publishes its own span for this
        # evaluation, so a client span would only duplicate it. Local runs don't
        # get that span in their trace, so they keep the client one.
        evaluate = (
            self._evaluate_guardrail
            if UiPathConfig.job_key
            else self._traced_evaluate_guardrail
        )
        return evaluate(
            input_data,
            guardrail,
            attachments=attachments,
            termination_mode=termination_mode,
            scope=scope,
            execution_stage=execution_stage,
            action_type=action_type,
        )

    @traced("evaluate_guardrail", run_type="uipath")
    def _traced_evaluate_guardrail(
        self,
        input_data: str | dict[str, Any],
        guardrail: BuiltInValidatorGuardrail,
        **options: Any,
    ) -> GuardrailValidationResult:
        return self._evaluate_guardrail(input_data, guardrail, **options)

    def _evaluate_guardrail(
        self,
        input_data: str | dict[str, Any],
        guardrail: BuiltInValidatorGuardrail,
        *,
        attachments: list[GuardrailAttachment] | None = None,
        termination_mode: GuardrailTerminationMode | None = None,
        scope: GuardrailScope | None = None,
        execution_stage: str | None = None,
        action_type: str | None = None,
    ) -> GuardrailValidationResult:
        spec = RequestSpec(
            method="POST",
            endpoint=Endpoint("/agentsruntime_/api/execution/guardrails/validate"),
            json=self._build_validate_payload(
                input_data,
                guardrail,
                attachments,
                termination_mode,
                scope=scope,
                execution_stage=execution_stage,
                action_type=action_type,
            ),
        )
        request_kwargs: dict[str, Any] = {
            "json": spec.json,
            "headers": self._build_validate_headers(spec, attachments),
            "timeout": _VALIDATE_TIMEOUT,
        }

        response_data, span_id = self._send_validate_request(
            spec, request_kwargs, guardrail.name
        )
        return self._to_validation_result(response_data, span_id, guardrail.name)

    @staticmethod
    def _build_validate_payload(
        input_data: str | dict[str, Any],
        guardrail: BuiltInValidatorGuardrail,
        attachments: list[GuardrailAttachment] | None,
        termination_mode: GuardrailTerminationMode | None,
        *,
        scope: GuardrailScope | None = None,
        execution_stage: str | None = None,
        action_type: str | None = None,
    ) -> dict[str, Any]:
        """Build the body of a validate request."""
        payload: dict[str, Any] = {
            "validator": guardrail.validator_type,
            "input": input_data if isinstance(input_data, str) else str(input_data),
            "parameters": [
                param.model_dump(by_alias=True)
                for param in guardrail.validator_parameters
            ],
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
        if scope is not None:
            payload["scope"] = scope.value
        if execution_stage is not None:
            payload["executionStage"] = execution_stage
        if action_type is not None:
            payload["actionType"] = action_type
        return payload

    def _build_validate_headers(
        self,
        spec: RequestSpec,
        attachments: list[GuardrailAttachment] | None,
    ) -> dict[str, str]:
        """Build the headers of a validate request.

        Includes trace context headers for server-side span correlation, plus
        the execution source (x-uipath-guardrails-source) and job key headers
        for licensing/metering correlation. The execution source is read from
        the execution context, propagated from the runtime context.
        """
        source_headers: dict[str, str] = {}
        execution_source = self._execution_context.execution_source
        if execution_source:
            source_headers[HEADER_GUARDRAILS_SOURCE] = execution_source
        folder_headers: dict[str, str] = {}
        if attachments and UiPathConfig.folder_key:
            folder_headers[HEADER_FOLDER_KEY] = UiPathConfig.folder_key
        return {
            **(spec.headers or {}),
            **build_trace_context_headers(extra_baggage=["source=agents"]),
            **source_headers,
            **header_job_key(),
            **folder_headers,
            HEADER_GUARDRAILS_TIMEOUT_MS: str(
                int(_VALIDATE_RESPONSE_TIMEOUT_SECONDS * 1000)
            ),
        }

    def _send_validate_request(
        self,
        spec: RequestSpec,
        request_kwargs: dict[str, Any],
        guardrail_name: str,
    ) -> tuple[dict[str, Any], str | None]:
        """Send a validate request; return the response body and the service span id."""
        try:
            response = _request_without_read_timeout_retry(
                self, spec.method, url=spec.endpoint, **request_kwargs
            )
        except ReadTimeout as e:
            raise GuardrailValidationTimeoutError(
                guardrail_name,
                _VALIDATE_RESPONSE_TIMEOUT_SECONDS,
                request=e.request,
            ) from e
        except EnrichedException as e:
            # The API returns 403 with a valid JSON body for ENTITLEMENTS_MISSING
            # or FEATURE_DISABLED; any other error is raised.
            if e.status_code != 403:
                raise
            # Read the full response from the original HTTPStatusError when
            # there is one, else parse the body kept on the exception.
            original_error = e.__cause__
            if isinstance(original_error, HTTPStatusError) and original_error.response:
                response = original_error.response
            else:
                return json.loads(e.response_content), None
        span_id = self._extract_span_id_from_traceparent(
            response.headers.get("x-uipath-traceparent-id")
        )
        return response.json(), span_id

    def _to_validation_result(
        self,
        response_data: dict[str, Any],
        span_id: str | None,
        guardrail_name: str,
    ) -> GuardrailValidationResult:
        """Map a validate response body to a GuardrailValidationResult."""
        result_str = response_data.get("result", "")
        reason = response_data.get("details", "")

        error_type = self._parse_error_type(result_str)
        if error_type is not None:
            # The service could not evaluate the input: fail closed so the
            # guardrail action still fires, and report why on error_type.
            logger.warning(
                "Guardrail '%s' could not be evaluated (%s): %s",
                guardrail_name,
                result_str,
                reason,
            )
            result = GuardrailValidationResultType.VALIDATION_FAILED
        else:
            result = self._parse_result(result_str)

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
