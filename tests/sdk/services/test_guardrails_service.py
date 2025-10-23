import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.guardrails_service import GuardrailsService
from uipath.models.guardrails import (
    BuiltInValidatorGuardrail,
    EnumListParameterValue,
    GuardrailScope,
    GuardrailSelector,
    MapEnumParameterValue,
)


@pytest.fixture
def service(
    config: Config, execution_context: ExecutionContext, monkeypatch: pytest.MonkeyPatch
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
                json={"validation_passed": True, "reason": "Validation passed"},
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
