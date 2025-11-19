from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.guardrails import (
    AllFieldsSelector,
    ApplyTo,
    BooleanOperator,
    BooleanRule,
    BuiltInValidatorGuardrail,
    CustomGuardrail,
    EnumListParameterValue,
    FieldReference,
    FieldSource,
    GuardrailScope,
    GuardrailSelector,
    MapEnumParameterValue,
    NumberOperator,
    NumberRule,
    SpecificFieldsSelector,
    UniversalRule,
    WordOperator,
    WordRule,
)
from uipath.platform.guardrails._guardrails_service import GuardrailsService


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

    class TestEvaluatePostCustomGuardrails:
        """Test evaluate_post_custom_guardrails method."""

        def test_evaluate_post_custom_guardrails_validation_passed(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test custom guardrail validation with passing rules."""
            # Create a custom guardrail matching the C# example
            custom_guardrail = CustomGuardrail(
                id="test-custom-id",
                name="Pre execution Guardrail",
                description="Test pre-execution guardrail",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    NumberRule(
                        rule_type="number",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(path="age", source=FieldSource.INPUT)
                            ],
                        ),
                        operator=NumberOperator.GREATER_THAN_OR_EQUAL,
                        value=21.0,
                    ),
                    BooleanRule(
                        rule_type="boolean",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(
                                    path="isActive", source=FieldSource.INPUT
                                )
                            ],
                        ),
                        operator=BooleanOperator.EQUALS,
                        value=True,
                    ),
                ],
            )

            # Input data matching the C# example
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=custom_guardrail,
            )

            assert result.validation_passed is True
            assert "All custom guardrail rules passed" in result.reason

        def test_evaluate_post_custom_guardrails_validation_failed_age(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test custom guardrail validation fails when age is too low."""
            custom_guardrail = CustomGuardrail(
                id="test-custom-id",
                name="Pre execution Guardrail",
                description="Test pre-execution guardrail",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    NumberRule(
                        rule_type="number",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(path="age", source=FieldSource.INPUT)
                            ],
                        ),
                        operator=NumberOperator.GREATER_THAN_OR_EQUAL,
                        value=21.0,
                    ),
                    BooleanRule(
                        rule_type="boolean",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(
                                    path="isActive", source=FieldSource.INPUT
                                )
                            ],
                        ),
                        operator=BooleanOperator.EQUALS,
                        value=True,
                    ),
                ],
            )

            # Input data with age < 21
            input_data = {
                "userName": "John",
                "age": 18,
                "isActive": True,
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=custom_guardrail,
            )

            assert result.validation_passed is False
            assert "age" in result.reason.lower()
            assert (
                "input data didn't match the guardrail condition: [age] greaterthanorequal [21.0]"
                in result.reason.lower()
            )

        def test_evaluate_post_custom_guardrails_validation_failed_is_active(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test custom guardrail validation fails when isActive is False."""
            custom_guardrail = CustomGuardrail(
                id="test-custom-id",
                name="Pre execution Guardrail",
                description="Test pre-execution guardrail",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    NumberRule(
                        rule_type="number",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(path="age", source=FieldSource.INPUT)
                            ],
                        ),
                        operator=NumberOperator.GREATER_THAN_OR_EQUAL,
                        value=21.0,
                    ),
                    BooleanRule(
                        rule_type="boolean",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(
                                    path="isActive", source=FieldSource.INPUT
                                )
                            ],
                        ),
                        operator=BooleanOperator.EQUALS,
                        value=True,
                    ),
                ],
            )

            # Input data with isActive = False
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": False,
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=custom_guardrail,
            )

            assert result.validation_passed is False
            assert "isActive" in result.reason or "isactive" in result.reason.lower()
            assert (
                "does not equal" in result.reason.lower()
                or "equals" in result.reason.lower()
            )

        def test_evaluate_post_custom_guardrails_matches_regex_positive(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test custom guardrail validation passes when regex matches."""
            custom_guardrail = CustomGuardrail(
                id="test-custom-id",
                name="Regex Guardrail",
                description="Test regex guardrail",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    WordRule(
                        rule_type="word",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(
                                    path="userName", source=FieldSource.INPUT
                                )
                            ],
                        ),
                        operator=WordOperator.MATCHES_REGEX,
                        value=".*te.*3.*",
                    ),
                ],
            )

            # Input data with userName that matches the regex pattern
            input_data = {
                "userName": "test123",
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=custom_guardrail,
            )

            assert result.validation_passed is True
            assert "All custom guardrail rules passed" in result.reason

        def test_evaluate_post_custom_guardrails_matches_regex_negative(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test custom guardrail validation fails when regex doesn't match."""
            custom_guardrail = CustomGuardrail(
                id="test-custom-id",
                name="Regex Guardrail",
                description="Test regex guardrail",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    WordRule(
                        rule_type="word",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(
                                    path="userName", source=FieldSource.INPUT
                                )
                            ],
                        ),
                        operator=WordOperator.MATCHES_REGEX,
                        value=".*te.*3.*",
                    ),
                ],
            )

            # Input data with userName that doesn't match the regex pattern
            input_data = {
                "userName": "test",
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=custom_guardrail,
            )

            assert result.validation_passed is False
            assert "userName" in result.reason
            assert "matchesregex" in result.reason.lower()

        def test_evaluate_post_custom_guardrails_word_func_positive(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test custom guardrail validation passes when word func returns True."""
            custom_guardrail = CustomGuardrail(
                id="test-custom-id",
                name="Word Func Guardrail",
                description="Test word func guardrail",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    WordRule(
                        rule_type="word",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(
                                    path="userName", source=FieldSource.INPUT
                                )
                            ],
                        ),
                        operator=WordOperator.FUNC,
                        value=None,
                        func=lambda s: len(s) > 5,
                    ),
                ],
            )

            # Input data with userName that passes the function check
            input_data = {
                "userName": "testuser",
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=custom_guardrail,
            )

            assert result.validation_passed is True
            assert "All custom guardrail rules passed" in result.reason

        def test_evaluate_post_custom_guardrails_word_func_negative(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test custom guardrail validation fails when word func returns False."""
            custom_guardrail = CustomGuardrail(
                id="test-custom-id",
                name="Word Func Guardrail",
                description="Test word func guardrail",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    WordRule(
                        rule_type="word",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(
                                    path="userName", source=FieldSource.INPUT
                                )
                            ],
                        ),
                        operator=WordOperator.FUNC,
                        value=None,
                        func=lambda s: len(s) > 5,
                    ),
                ],
            )

            # Input data with userName that fails the function check
            input_data = {
                "userName": "test",
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=custom_guardrail,
            )

            assert result.validation_passed is False

        def test_evaluate_post_custom_guardrails_number_func_positive(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test custom guardrail validation passes when number func returns True."""
            custom_guardrail = CustomGuardrail(
                id="test-custom-id",
                name="Number Func Guardrail",
                description="Test number func guardrail",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    NumberRule(
                        rule_type="number",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(path="age", source=FieldSource.INPUT)
                            ],
                        ),
                        operator=NumberOperator.FUNC,
                        value=0.0,
                        func=lambda n: n >= 18 and n <= 65,
                    ),
                ],
            )

            # Input data with age that passes the function check
            input_data = {
                "age": 25,
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=custom_guardrail,
            )

            assert result.validation_passed is True
            assert "All custom guardrail rules passed" in result.reason

        def test_evaluate_post_custom_guardrails_number_func_negative(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test custom guardrail validation fails when number func returns False."""
            custom_guardrail = CustomGuardrail(
                id="test-custom-id",
                name="Number Func Guardrail",
                description="Test number func guardrail",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    NumberRule(
                        rule_type="number",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(path="age", source=FieldSource.INPUT)
                            ],
                        ),
                        operator=NumberOperator.FUNC,
                        value=0.0,
                        func=lambda n: n >= 18 and n <= 65,
                    ),
                ],
            )

            # Input data with age that fails the function check
            input_data = {
                "age": 70,
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=custom_guardrail,
            )

            assert result.validation_passed is False

        def test_should_trigger_policy_pre_execution_only_some_rules_not_met_returns_false(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test pre-execution guardrail fails when some rules are not met."""
            guardrail = self._create_guardrail_for_pre_execution()
            input_data = {
                "userName": "John",
                "age": 18,  # Less than 21
                "isActive": True,
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is False

        def test_should_ignore_post_execution_guardrail_for_pre_execution_returns_false(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test that pre-execution guardrail ignores post-execution data."""
            guardrail = self._create_guardrail_for_post_execution()
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            # Should fail because post-execution guardrail needs output data
            assert result.validation_passed is True

        def test_should_trigger_policy_post_execution_guardrail_for_pre_execution_returns_false(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test that pre-execution guardrail does not trigger in post-execution."""
            guardrail = self._create_guardrail_for_pre_execution()
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data = {
                "result": "Success",
                "status": 200,
                "success": True,
            }

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            # Pre-execution guardrail should still pass in post-execution
            assert result.validation_passed is True

        def test_should_trigger_policy_post_execution_with_output_fields_all_conditions_met_returns_true(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test post-execution guardrail passes when all conditions are met."""
            guardrail = self._create_guardrail_for_post_execution()
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data = {
                "result": "Success",
                "status": 200,
                "success": True,
            }

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is True

        def test_should_trigger_policy_post_execution_with_output_fields_input_conditions_not_met_returns_false(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test post-execution guardrail fails when input conditions are not met."""
            guardrail = self._create_guardrail_for_post_execution()
            input_data = {
                "userName": "John",
                "age": 18,  # Less than 21
                "isActive": True,
            }
            output_data = {
                "result": "Success",
                "status": 200,
                "success": True,
            }

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is False

        def test_should_trigger_policy_post_execution_with_output_fields_output_conditions_not_met_returns_false(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test post-execution guardrail fails when output conditions are not met."""
            guardrail = self._create_guardrail_for_post_execution()
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data = {
                "result": "Success",
                "status": 400,  # Not 200
                "success": True,
            }

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is False

        def test_should_trigger_policy_post_execution_multiple_rules_all_conditions_must_be_met_returns_true(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test post-execution guardrail with multiple rules passes when all conditions are met."""
            guardrail = self._create_guardrail_with_multiple_rules()
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data = {
                "result": "Success",
                "status": 200,
                "success": True,
            }

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is True

        def test_should_trigger_policy_post_execution_rule_with_multiple_conditions_all_must_be_met_returns_true(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test guardrail with rule having multiple conditions passes when all are met."""
            guardrail = self._create_guardrail_with_rule_having_multiple_conditions()
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data = {
                "result": "Success",
                "status": 200,
                "success": True,
            }

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is True

        def test_should_trigger_policy_post_execution_rule_with_multiple_conditions_one_condition_not_met_returns_false(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test guardrail with multiple conditions fails when one condition is not met."""
            guardrail = self._create_guardrail_with_rule_having_multiple_conditions()
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": False,  # Not True
            }
            output_data = {
                "result": "Success",
                "status": 200,
                "success": True,
            }

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is False

        def test_should_trigger_policy_post_execution_with_all_fields_selector_output_schema_has_fields_returns_true(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test guardrail with AllFieldsSelector passes when output has matching fields."""
            guardrail = CustomGuardrail(
                id="test-all-fields-id",
                name="Guardrail With All Fields Selector",
                description="Test all fields selector",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    NumberRule(
                        rule_type="number",
                        field_selector=AllFieldsSelector(selector_type="all"),
                        operator=NumberOperator.EQUALS,
                        value=25.0,
                    ),
                ],
            )

            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data = {
                "result": "Success",
                "status": 25,  # Matches the rule value
                "success": True,
            }

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is True

        def test_should_trigger_policy_post_execution_with_all_fields_selector_empty_output_schema_returns_false(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test guardrail with AllFieldsSelector fails when output is empty."""
            guardrail = CustomGuardrail(
                id="test-all-fields-id",
                name="Guardrail With All Fields Selector",
                description="Test all fields selector",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    NumberRule(
                        rule_type="number",
                        field_selector=AllFieldsSelector(selector_type="all"),
                        operator=NumberOperator.EQUALS,
                        value=200.0,
                    ),
                ],
            )

            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data: dict[str, Any] = {}  # Empty output

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is False

        def test_should_trigger_policy_pre_execution_always_rule_with_input_apply_to_returns_true(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test UniversalRule with INPUT ApplyTo triggers in pre-execution."""
            guardrail = self._create_guardrail_with_always_rule(ApplyTo.INPUT)
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is False  # Should trigger

        def test_should_trigger_policy_pre_execution_always_rule_with_output_apply_to_returns_false(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test UniversalRule with OUTPUT ApplyTo does not trigger in pre-execution."""
            guardrail = self._create_guardrail_with_always_rule(ApplyTo.OUTPUT)
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is True  # Should not trigger

        def test_should_trigger_policy_pre_execution_always_rule_with_input_and_output_apply_to_returns_true(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test UniversalRule with INPUT_AND_OUTPUT ApplyTo triggers in pre-execution."""
            guardrail = self._create_guardrail_with_always_rule(
                ApplyTo.INPUT_AND_OUTPUT
            )
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data: dict[str, Any] = {}

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is False  # Should trigger

        def test_should_trigger_policy_post_execution_always_rule_with_input_apply_to_returns_false(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test UniversalRule with INPUT ApplyTo does not trigger in post-execution."""
            guardrail = self._create_guardrail_with_always_rule(ApplyTo.INPUT)
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data = {
                "result": "Success",
                "status": 200,
                "success": True,
            }

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is True  # Should not trigger

        def test_should_trigger_policy_post_execution_always_rule_with_output_apply_to_returns_true(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test UniversalRule with OUTPUT ApplyTo triggers in post-execution."""
            guardrail = self._create_guardrail_with_always_rule(ApplyTo.OUTPUT)
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data = {
                "result": "Success",
                "status": 200,
                "success": True,
            }

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is False  # Should trigger

        def test_should_trigger_policy_post_execution_always_rule_with_input_and_output_apply_to_returns_true(
            self,
            service: GuardrailsService,
        ) -> None:
            """Test UniversalRule with INPUT_AND_OUTPUT ApplyTo triggers in post-execution."""
            guardrail = self._create_guardrail_with_always_rule(
                ApplyTo.INPUT_AND_OUTPUT
            )
            input_data = {
                "userName": "John",
                "age": 25,
                "isActive": True,
            }
            output_data = {
                "result": "Success",
                "status": 200,
                "success": True,
            }

            result = service.evaluate_post_custom_guardrails(
                input_data=input_data,
                output_data=output_data,
                guardrail=guardrail,
            )

            assert result.validation_passed is False  # Should trigger

        # Helper methods to create guardrails
        def _create_guardrail_for_pre_execution(self) -> CustomGuardrail:
            """Create a guardrail for pre-execution testing."""
            return CustomGuardrail(
                id="test-pre-exec-id",
                name="Pre execution Guardrail",
                description="Test pre-execution guardrail",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    NumberRule(
                        rule_type="number",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(path="age", source=FieldSource.INPUT)
                            ],
                        ),
                        operator=NumberOperator.GREATER_THAN_OR_EQUAL,
                        value=21.0,
                    ),
                    BooleanRule(
                        rule_type="boolean",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(
                                    path="isActive", source=FieldSource.INPUT
                                )
                            ],
                        ),
                        operator=BooleanOperator.EQUALS,
                        value=True,
                    ),
                ],
            )

        def _create_guardrail_for_post_execution(self) -> CustomGuardrail:
            """Create a guardrail for post-execution testing."""
            return CustomGuardrail(
                id="test-post-exec-id",
                name="Guardrail for Post execution",
                description="Test post-execution guardrail",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    NumberRule(
                        rule_type="number",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(path="age", source=FieldSource.INPUT)
                            ],
                        ),
                        operator=NumberOperator.GREATER_THAN_OR_EQUAL,
                        value=21.0,
                    ),
                    NumberRule(
                        rule_type="number",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(path="status", source=FieldSource.OUTPUT)
                            ],
                        ),
                        operator=NumberOperator.EQUALS,
                        value=200.0,
                    ),
                ],
            )

        def _create_guardrail_with_multiple_rules(self) -> CustomGuardrail:
            """Create a guardrail with multiple rules."""
            return CustomGuardrail(
                id="test-multiple-rules-id",
                name="Guardrail With Multiple Rules",
                description="Test guardrail with multiple rules",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    NumberRule(
                        rule_type="number",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(path="age", source=FieldSource.INPUT)
                            ],
                        ),
                        operator=NumberOperator.GREATER_THAN_OR_EQUAL,
                        value=21.0,
                    ),
                    BooleanRule(
                        rule_type="boolean",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(
                                    path="isActive", source=FieldSource.INPUT
                                )
                            ],
                        ),
                        operator=BooleanOperator.EQUALS,
                        value=True,
                    ),
                    NumberRule(
                        rule_type="number",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(path="status", source=FieldSource.OUTPUT)
                            ],
                        ),
                        operator=NumberOperator.EQUALS,
                        value=200.0,
                    ),
                ],
            )

        def _create_guardrail_with_rule_having_multiple_conditions(
            self,
        ) -> CustomGuardrail:
            """Create a guardrail with rule having multiple conditions."""
            return CustomGuardrail(
                id="test-multiple-conditions-id",
                name="Guardrail With Rule Having Multiple Conditions",
                description="Test guardrail with multiple conditions",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    NumberRule(
                        rule_type="number",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(path="age", source=FieldSource.INPUT)
                            ],
                        ),
                        operator=NumberOperator.GREATER_THAN_OR_EQUAL,
                        value=21.0,
                    ),
                    BooleanRule(
                        rule_type="boolean",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(
                                    path="isActive", source=FieldSource.INPUT
                                )
                            ],
                        ),
                        operator=BooleanOperator.EQUALS,
                        value=True,
                    ),
                    NumberRule(
                        rule_type="number",
                        field_selector=SpecificFieldsSelector(
                            selector_type="specific",
                            fields=[
                                FieldReference(path="status", source=FieldSource.OUTPUT)
                            ],
                        ),
                        operator=NumberOperator.EQUALS,
                        value=200.0,
                    ),
                ],
            )

        def _create_guardrail_with_always_rule(
            self, apply_to: ApplyTo
        ) -> CustomGuardrail:
            """Create a guardrail with an AlwaysRule (UniversalRule)."""
            return CustomGuardrail(
                id="test-always-rule-id",
                name="Guardrail With Always Rule",
                description="Test guardrail with always rule",
                enabled_for_evals=True,
                guardrail_type="custom",
                selector=GuardrailSelector(
                    scopes=[GuardrailScope.TOOL], match_names=["test"]
                ),
                rules=[
                    UniversalRule(
                        rule_type="always",
                        apply_to=apply_to,
                    ),
                ],
            )
