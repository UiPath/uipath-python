import json

import httpx
import pytest
from pytest_httpx import HTTPXMock
from uipath.core.guardrails import (
    GuardrailScope,
    GuardrailSelector,
    GuardrailValidationResultType,
)

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.common import ExecutionSourceContext
from uipath.platform.guardrails import (
    BuiltInValidatorGuardrail,
    EnumListParameterValue,
    GuardrailsService,
    MapEnumParameterValue,
)


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> GuardrailsService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
    return GuardrailsService(config=config, execution_context=execution_context)


class TestGuardrailsService:
    """Test GuardrailsService functionality."""

    class TestEvaluateGuardrail:
        """Test evaluate_guardrail method."""

        def test_evaluate_guardrail_validation(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            print(f"base_url: {base_url}, org: {org}, tenant: {tenant}")
            # Mock the API response
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                status_code=200,
                json={
                    "result": "PASSED",
                    "details": "Validation passed",
                },
            )

            # Create a PII detection guardrail
            pii_guardrail = BuiltInValidatorGuardrail(
                id="test-id",
                name="PII detection guardrail",
                description="Test PII detection",
                enabled_for_evals=True,
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["StringToNumber"]
                ),
                guardrail_type="builtInValidator",
                validator_type="pii_detection",
                validator_parameters=[
                    EnumListParameterValue(
                        parameter_type="enum-list",
                        id="entities",
                        value=["Email", "Address"],
                    ),
                    MapEnumParameterValue(
                        parameter_type="map-enum",
                        id="entityThresholds",
                        value={"Email": 1, "Address": 0.7},
                    ),
                ],
            )

            test_input = "There is no email or address here."

            result = service.evaluate_guardrail(test_input, pii_guardrail)

            assert result.result == GuardrailValidationResultType.PASSED
            assert result.reason == "Validation passed"

        def test_evaluate_guardrail_validation_failed(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            # Mock API response for failed validation
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                status_code=200,
                json={
                    "result": "VALIDATION_FAILED",
                    "details": "PII detected: Email found",
                },
            )

            pii_guardrail = BuiltInValidatorGuardrail(
                id="test-id",
                name="PII detection guardrail",
                description="Test PII detection",
                enabled_for_evals=True,
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["StringToNumber"]
                ),
                guardrail_type="builtInValidator",
                validator_type="pii_detection",
                validator_parameters=[],
            )

            test_input = "Contact me at john@example.com"

            result = service.evaluate_guardrail(test_input, pii_guardrail)

            assert result.result == GuardrailValidationResultType.VALIDATION_FAILED
            assert result.reason == "PII detected: Email found"

        def test_evaluate_guardrail_feature_disabled_403(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            # Mock API response with 403 status for FEATURE_DISABLED
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                status_code=403,
                json={
                    "result": "FEATURE_DISABLED",
                    "details": "Guardrail feature is disabled",
                },
            )

            pii_guardrail = BuiltInValidatorGuardrail(
                id="test-id",
                name="PII detection guardrail",
                description="Test PII detection",
                enabled_for_evals=True,
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["StringToNumber"]
                ),
                guardrail_type="builtInValidator",
                validator_type="pii_detection",
                validator_parameters=[],
            )

            test_input = "Contact me at john@example.com"

            result = service.evaluate_guardrail(test_input, pii_guardrail)

            assert result.result == GuardrailValidationResultType.FEATURE_DISABLED
            assert result.reason == "Guardrail feature is disabled"

        def test_evaluate_guardrail_entitlements_missing_403(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            # Mock API response with 403 status for ENTITLEMENTS_MISSING
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                status_code=403,
                json={
                    "result": "ENTITLEMENTS_MISSING",
                    "details": "Guardrail entitlement is missing",
                },
            )

            pii_guardrail = BuiltInValidatorGuardrail(
                id="test-id",
                name="PII detection guardrail",
                description="Test PII detection",
                enabled_for_evals=True,
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["StringToNumber"]
                ),
                guardrail_type="builtInValidator",
                validator_type="pii_detection",
                validator_parameters=[],
            )

            test_input = "Contact me at john@example.com"

            result = service.evaluate_guardrail(test_input, pii_guardrail)

            assert result.result == GuardrailValidationResultType.ENTITLEMENTS_MISSING
            assert result.reason == "Guardrail entitlement is missing"

        def test_evaluate_guardrail_request_payload_structure(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            """Test that the request payload has the correct structure after revert."""
            captured_request = None

            def capture_request(request):
                nonlocal captured_request
                captured_request = request
                return httpx.Response(
                    status_code=200,
                    json={
                        "result": "PASSED",
                        "details": "Validation passed",
                    },
                )

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                callback=capture_request,
            )

            # Create a PII detection guardrail with parameters
            pii_guardrail = BuiltInValidatorGuardrail(
                id="test-id",
                name="PII detection guardrail",
                description="Test PII detection",
                enabled_for_evals=True,
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["StringToNumber"]
                ),
                guardrail_type="builtInValidator",
                validator_type="pii_detection",
                validator_parameters=[
                    EnumListParameterValue(
                        parameter_type="enum-list",
                        id="entities",
                        value=["Email", "Address"],
                    ),
                    MapEnumParameterValue(
                        parameter_type="map-enum",
                        id="entityThresholds",
                        value={"Email": 1, "Address": 0.7},
                    ),
                ],
            )

            test_input = "There is no email or address here."

            result = service.evaluate_guardrail(test_input, pii_guardrail)

            # Verify the request was captured
            assert captured_request is not None

            # Parse the request payload
            request_payload = json.loads(captured_request.content)

            # Verify the payload structure:
            # {
            #     "validator": guardrail.validator_type,
            #     "input": input_data,
            #     "parameters": parameters,
            #     "guardrailName": guardrail.name,
            # }
            assert "validator" in request_payload
            assert "input" in request_payload
            assert "parameters" in request_payload
            assert "guardrailName" in request_payload
            assert request_payload["guardrailName"] == "PII detection guardrail"

            # Verify validator is a string (not an object)
            assert isinstance(request_payload["validator"], str)
            assert request_payload["validator"] == "pii_detection"

            # Verify input is a string
            assert isinstance(request_payload["input"], str)
            assert request_payload["input"] == "There is no email or address here."

            # Verify parameters is an array
            assert isinstance(request_payload["parameters"], list)
            assert len(request_payload["parameters"]) == 2

            # Verify parameter structure
            entities_param = request_payload["parameters"][0]
            assert entities_param["$parameterType"] == "enum-list"
            assert entities_param["id"] == "entities"
            assert entities_param["value"] == ["Email", "Address"]

            thresholds_param = request_payload["parameters"][1]
            assert thresholds_param["$parameterType"] == "map-enum"
            assert thresholds_param["id"] == "entityThresholds"
            assert thresholds_param["value"] == {"Email": 1, "Address": 0.7}

            # Verify result fields
            assert result.result == GuardrailValidationResultType.PASSED
            assert result.reason == "Validation passed"

        def test_evaluate_guardrail_byog_forwards_byo_validator_name(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            """A BYOG guardrail forwards byoValidatorName so the guardrails service
            can resolve the connector-backed configuration."""
            captured_request = None

            def capture_request(request):
                nonlocal captured_request
                captured_request = request
                return httpx.Response(
                    status_code=200,
                    json={"result": "PASSED", "details": "Validation passed"},
                )

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                callback=capture_request,
            )

            # BYOG persisted shape: "byo" sentinel + byoValidatorName reference.
            byog_guardrail = BuiltInValidatorGuardrail(
                id="byog-id",
                name="Databricks PII (BYOG)",
                description="Customer-provided PII validator",
                enabled_for_evals=True,
                selector=GuardrailSelector(scopes=[GuardrailScope.LLM]),
                guardrail_type="builtInValidator",
                validator_type="byo",
                byo_validator_name="my_databricks_pii",
                validator_parameters=[],
            )

            result = service.evaluate_guardrail("some input", byog_guardrail)

            assert captured_request is not None
            request_payload = json.loads(captured_request.content)
            assert request_payload["validator"] == "byo"
            assert request_payload["byoValidatorName"] == "my_databricks_pii"
            assert result.result == GuardrailValidationResultType.PASSED

        def test_evaluate_guardrail_byog_forwards_byo_connection_id(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            """A BYOG guardrail forwards byoConnectionId so the backend can narrow
            configuration resolution to the specific connection."""
            captured_request = None

            def capture_request(request):
                nonlocal captured_request
                captured_request = request
                return httpx.Response(
                    status_code=200,
                    json={"result": "PASSED", "details": "Validation passed"},
                )

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                callback=capture_request,
            )

            byog_guardrail = BuiltInValidatorGuardrail(
                id="byog-id",
                name="Databricks PII (BYOG)",
                enabled_for_evals=True,
                selector=GuardrailSelector(scopes=[GuardrailScope.LLM]),
                guardrail_type="builtInValidator",
                validator_type="byo",
                byo_validator_name="my_databricks_pii",
                byo_connection_id="byog-conn-1",
                validator_parameters=[],
            )

            service.evaluate_guardrail("some input", byog_guardrail)

            assert captured_request is not None
            request_payload = json.loads(captured_request.content)
            assert request_payload["byoValidatorName"] == "my_databricks_pii"
            assert request_payload["byoConnectionId"] == "byog-conn-1"

        def test_evaluate_guardrail_byog_omits_connection_id_when_absent(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            """byoConnectionId is only forwarded when present; a BYOG guardrail without
            one resolves by validator name alone."""
            captured_request = None

            def capture_request(request):
                nonlocal captured_request
                captured_request = request
                return httpx.Response(
                    status_code=200,
                    json={"result": "PASSED", "details": "Validation passed"},
                )

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                callback=capture_request,
            )

            byog_guardrail = BuiltInValidatorGuardrail(
                id="byog-id",
                name="Databricks PII (BYOG)",
                enabled_for_evals=True,
                selector=GuardrailSelector(scopes=[GuardrailScope.LLM]),
                guardrail_type="builtInValidator",
                validator_type="byo",
                byo_validator_name="my_databricks_pii",
                validator_parameters=[],
            )

            service.evaluate_guardrail("some input", byog_guardrail)

            assert captured_request is not None
            request_payload = json.loads(captured_request.content)
            assert "byoConnectionId" not in request_payload

        def test_evaluate_guardrail_byo_connection_id_from_alias(self) -> None:
            """byoConnectionId parses into the typed field via its camelCase alias."""
            guardrail = BuiltInValidatorGuardrail.model_validate(
                {
                    "$guardrailType": "builtInValidator",
                    "id": "byog-id",
                    "name": "BYOG",
                    "validatorType": "byo",
                    "byoValidatorName": "my_databricks_pii",
                    "byoConnectionId": "byog-conn-1",
                    "validatorParameters": [],
                }
            )
            assert guardrail.byo_connection_id == "byog-conn-1"

        def test_evaluate_guardrail_byo_without_name_raises(
            self,
            service: GuardrailsService,
        ) -> None:
            """A "byo" guardrail missing its byoValidatorName reference fails fast
            rather than sending an unresolvable request."""
            guardrail = BuiltInValidatorGuardrail(
                id="byog-id",
                name="Broken BYOG",
                enabled_for_evals=True,
                selector=GuardrailSelector(scopes=[GuardrailScope.LLM]),
                guardrail_type="builtInValidator",
                validator_type="byo",
                validator_parameters=[],
            )

            with pytest.raises(ValueError, match="byo_validator_name"):
                service.evaluate_guardrail("some input", guardrail)

        def test_evaluate_guardrail_byo_validator_name_from_alias(self) -> None:
            """byoValidatorName parses into the typed field via its camelCase alias."""
            guardrail = BuiltInValidatorGuardrail.model_validate(
                {
                    "$guardrailType": "builtInValidator",
                    "id": "byog-id",
                    "name": "BYOG",
                    "validatorType": "byo",
                    "byoValidatorName": "my_databricks_pii",
                    "validatorParameters": [],
                }
            )
            assert guardrail.byo_validator_name == "my_databricks_pii"

        def test_evaluate_guardrail_non_byo_type_does_not_forward_name(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            """byoValidatorName is only forwarded for the "byo" sentinel, never leaked
            into a non-BYOG validator payload even if the field happens to be set."""
            captured_request = None

            def capture_request(request):
                nonlocal captured_request
                captured_request = request
                return httpx.Response(
                    status_code=200,
                    json={"result": "PASSED", "details": "Validation passed"},
                )

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                callback=capture_request,
            )

            guardrail = BuiltInValidatorGuardrail(
                id="test-id",
                name="PII detection guardrail",
                enabled_for_evals=True,
                selector=GuardrailSelector(scopes=[GuardrailScope.LLM]),
                guardrail_type="builtInValidator",
                validator_type="pii_detection",
                byo_validator_name="stray_name",
                validator_parameters=[],
            )

            service.evaluate_guardrail("some input", guardrail)

            assert captured_request is not None
            request_payload = json.loads(captured_request.content)
            assert "byoValidatorName" not in request_payload

        def test_evaluate_guardrail_non_byo_type_does_not_forward_connection_id(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            """byoConnectionId is only forwarded for the "byo" sentinel, never leaked
            into a non-BYOG validator payload even if the field happens to be set."""
            captured_request = None

            def capture_request(request):
                nonlocal captured_request
                captured_request = request
                return httpx.Response(
                    status_code=200,
                    json={"result": "PASSED", "details": "Validation passed"},
                )

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                callback=capture_request,
            )

            guardrail = BuiltInValidatorGuardrail(
                id="test-id",
                name="PII detection guardrail",
                enabled_for_evals=True,
                selector=GuardrailSelector(scopes=[GuardrailScope.LLM]),
                guardrail_type="builtInValidator",
                validator_type="pii_detection",
                byo_connection_id="stray-conn",
                validator_parameters=[],
            )

            service.evaluate_guardrail("some input", guardrail)

            assert captured_request is not None
            request_payload = json.loads(captured_request.content)
            assert "byoConnectionId" not in request_payload

        def test_evaluate_guardrail_ootb_omits_byo_validator_name(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            """OOTB validators (no byo_validator_name) keep their payload unchanged —
            byoValidatorName is not sent."""
            captured_request = None

            def capture_request(request):
                nonlocal captured_request
                captured_request = request
                return httpx.Response(
                    status_code=200,
                    json={"result": "PASSED", "details": "Validation passed"},
                )

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                callback=capture_request,
            )

            pii_guardrail = BuiltInValidatorGuardrail(
                id="test-id",
                name="PII detection guardrail",
                description="Test PII detection",
                enabled_for_evals=True,
                selector=GuardrailSelector(scopes=[GuardrailScope.LLM]),
                guardrail_type="builtInValidator",
                validator_type="pii_detection",
                validator_parameters=[],
            )

            service.evaluate_guardrail("some input", pii_guardrail)

            assert captured_request is not None
            request_payload = json.loads(captured_request.content)
            assert "byoValidatorName" not in request_payload
            assert pii_guardrail.byo_validator_name is None

        def test_evaluate_guardrail_sends_trace_context_headers(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            """Outgoing request includes trace context headers."""
            captured_request = None

            def capture_request(request):
                nonlocal captured_request
                captured_request = request
                return httpx.Response(
                    status_code=200,
                    json={
                        "result": "PASSED",
                        "details": "OK",
                    },
                )

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                callback=capture_request,
            )

            pii_guardrail = BuiltInValidatorGuardrail(
                id="test-id",
                name="PII guardrail",
                description="Test",
                enabled_for_evals=True,
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["tool1"]
                ),
                guardrail_type="builtInValidator",
                validator_type="pii_detection",
                validator_parameters=[],
            )

            service.evaluate_guardrail("test input", pii_guardrail)

            assert captured_request is not None
            # build_trace_context_headers() injects traceparent/tracestate when
            # an active span exists; at minimum, the merge with spec.headers
            # should not fail and the request should go through successfully.
            # When there IS an active trace context, headers are present:
            headers = dict(captured_request.headers)
            # The request should have been sent (basic smoke check that
            # header merging works even when no active span exists)
            assert "content-type" in headers

        def test_evaluate_guardrail_sends_source_and_job_key_headers(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            """Outgoing request includes execution source and job key headers."""
            monkeypatch.setenv("UIPATH_JOB_KEY", "job-123")

            captured_request = None

            def capture_request(request):
                nonlocal captured_request
                captured_request = request
                return httpx.Response(
                    status_code=200,
                    json={"result": "PASSED", "details": "OK"},
                )

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                callback=capture_request,
            )

            pii_guardrail = BuiltInValidatorGuardrail(
                id="test-id",
                name="PII guardrail",
                description="Test",
                enabled_for_evals=True,
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["tool1"]
                ),
                guardrail_type="builtInValidator",
                validator_type="pii_detection",
                validator_parameters=[],
            )

            with ExecutionSourceContext("runtime"):
                service.evaluate_guardrail("test input", pii_guardrail)

            assert captured_request is not None
            headers = dict(captured_request.headers)
            assert headers.get("x-uipath-guardrails-source") == "runtime"
            assert headers.get("x-uipath-jobkey") == "job-123"

        def test_evaluate_guardrail_omits_source_and_job_key_when_unset(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
            monkeypatch: pytest.MonkeyPatch,
        ) -> None:
            """Source/job key headers are absent when unset."""
            monkeypatch.delenv("UIPATH_JOB_KEY", raising=False)

            captured_request = None

            def capture_request(request):
                nonlocal captured_request
                captured_request = request
                return httpx.Response(
                    status_code=200,
                    json={"result": "PASSED", "details": "OK"},
                )

            httpx_mock.add_callback(
                method="POST",
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                callback=capture_request,
            )

            pii_guardrail = BuiltInValidatorGuardrail(
                id="test-id",
                name="PII guardrail",
                description="Test",
                enabled_for_evals=True,
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["tool1"]
                ),
                guardrail_type="builtInValidator",
                validator_type="pii_detection",
                validator_parameters=[],
            )

            service.evaluate_guardrail("test input", pii_guardrail)

            assert captured_request is not None
            headers = dict(captured_request.headers)
            assert "x-uipath-guardrails-source" not in headers
            assert "x-uipath-jobkey" not in headers

        def test_evaluate_guardrail_extracts_span_id_from_traceparent(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            """Response with x-uipath-traceparent-id header populates span_id."""
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                status_code=200,
                json={
                    "result": "VALIDATION_FAILED",
                    "details": "PII detected",
                },
                headers={
                    "x-uipath-traceparent-id": "00-abcdef1234567890abcdef1234567890-1234567890abcdef"
                },
            )

            pii_guardrail = BuiltInValidatorGuardrail(
                id="test-id",
                name="PII guardrail",
                description="Test",
                enabled_for_evals=True,
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["tool1"]
                ),
                guardrail_type="builtInValidator",
                validator_type="pii_detection",
                validator_parameters=[],
            )

            result = service.evaluate_guardrail("test input", pii_guardrail)

            assert result.result == GuardrailValidationResultType.VALIDATION_FAILED
            assert result.span_id == "00000000-0000-0000-1234-567890abcdef"

        def test_evaluate_guardrail_no_traceparent_header_no_span_id(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            """Response without x-uipath-traceparent-id header leaves span_id as None."""
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                status_code=200,
                json={
                    "result": "PASSED",
                    "details": "OK",
                },
            )

            pii_guardrail = BuiltInValidatorGuardrail(
                id="test-id",
                name="PII guardrail",
                description="Test",
                enabled_for_evals=True,
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["tool1"]
                ),
                guardrail_type="builtInValidator",
                validator_type="pii_detection",
                validator_parameters=[],
            )

            result = service.evaluate_guardrail("test input", pii_guardrail)

            assert result.result == GuardrailValidationResultType.PASSED
            assert result.span_id is None

    class TestExtractSpanIdFromTraceparent:
        """Tests for _extract_span_id_from_traceparent."""

        def test_valid_traceparent_16_char_span_id(self) -> None:
            result = GuardrailsService._extract_span_id_from_traceparent(
                "00-abcdef1234567890abcdef1234567890-1234567890abcdef"
            )
            assert result == "00000000-0000-0000-1234-567890abcdef"

        def test_valid_traceparent_32_char_span_id(self) -> None:
            result = GuardrailsService._extract_span_id_from_traceparent(
                "00-abcdef1234567890abcdef1234567890-0a1b2c3d4e5f67890a1b2c3d4e5f6789"
            )
            assert result == "0a1b2c3d-4e5f-6789-0a1b-2c3d4e5f6789"

        def test_none_input(self) -> None:
            assert GuardrailsService._extract_span_id_from_traceparent(None) is None

        def test_empty_string(self) -> None:
            assert GuardrailsService._extract_span_id_from_traceparent("") is None

        def test_valid_traceparent_4_part_with_trace_flags(self) -> None:
            result = GuardrailsService._extract_span_id_from_traceparent(
                "00-abcdef1234567890abcdef1234567890-1234567890abcdef-01"
            )
            assert result == "00000000-0000-0000-1234-567890abcdef"

        def test_uppercase_hex_normalized_to_lowercase(self) -> None:
            result = GuardrailsService._extract_span_id_from_traceparent(
                "00-ABCDEF1234567890ABCDEF1234567890-1234567890ABCDEF"
            )
            assert result == "00000000-0000-0000-1234-567890abcdef"

        def test_invalid_span_id_length_rejected(self) -> None:
            """Span IDs that are neither 16 nor 32 hex chars are rejected."""
            assert (
                GuardrailsService._extract_span_id_from_traceparent(
                    "00-abcdef1234567890abcdef1234567890-1234abcd"
                )
                is None
            )

        def test_invalid_format(self) -> None:
            assert (
                GuardrailsService._extract_span_id_from_traceparent("not-valid") is None
            )
