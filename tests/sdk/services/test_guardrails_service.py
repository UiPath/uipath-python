import json

import httpx
import pytest
from pytest_httpx import HTTPXMock
from uipath.core.guardrails import (
    GuardrailScope,
    GuardrailSelector,
)

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
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
                    "validation_passed": True,
                    "reason": "Validation passed",
                    "skip": False,
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

            assert result.validation_passed is True
            assert result.reason == "Validation passed"
            # If skip field exists, new API is deployed - check result and details
            if hasattr(result, "skip"):
                assert result.skip is False
                assert result.result == "passed"
                assert result.details == "Validation passed"

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
                    "validation_passed": False,
                    "reason": "PII detected: Email found",
                    "skip": False,
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

            assert result.validation_passed is False
            assert result.reason == "PII detected: Email found"
            # If skip field exists, new API is deployed - check result and details
            if hasattr(result, "skip"):
                assert result.skip is False
                assert result.result == "failed"
                assert result.details == "PII detected: Email found"

        def test_evaluate_guardrail_entitlements_skip(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            # Mock API response for entitlements check - feature disabled
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                status_code=200,
                json={
                    "validation_passed": True,
                    "reason": "Guardrail feature is disabled",
                    "skip": True,
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

            assert result.validation_passed is True
            assert result.reason == "Guardrail feature is disabled"
            # If skip field exists, new API is deployed - check result and details
            if hasattr(result, "skip"):
                assert result.skip is True
                assert result.result == "skipped"
                assert result.details == "Guardrail feature is disabled"

        def test_evaluate_guardrail_entitlements_missing(
            self,
            httpx_mock: HTTPXMock,
            service: GuardrailsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            # Mock API response for entitlements check - entitlement missing
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/agentsruntime_/api/execution/guardrails/validate",
                status_code=200,
                json={
                    "validation_passed": True,
                    "reason": "Guardrail entitlement is missing",
                    "skip": True,
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

            assert result.validation_passed is True
            assert result.reason == "Guardrail entitlement is missing"
            # If skip field exists, new API is deployed - check result and details
            if hasattr(result, "skip"):
                assert result.skip is True
                assert result.result == "skipped"
                assert result.details == "Guardrail entitlement is missing"

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
                        "validation_passed": True,
                        "reason": "Validation passed",
                        "skip": False,
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

            # Verify the payload structure matches the reverted format:
            # {
            #     "validator": guardrail.validator_type,
            #     "input": input_data,
            #     "parameters": parameters,
            # }
            assert "validator" in request_payload
            assert "input" in request_payload
            assert "parameters" in request_payload

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
            assert result.validation_passed is True
            # If skip field exists, new API is deployed - check result and details
            if hasattr(result, "skip"):
                assert result.skip is False
                assert result.result == "passed"
                assert result.details == "Validation passed"
