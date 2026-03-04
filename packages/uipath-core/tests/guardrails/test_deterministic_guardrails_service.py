import re
from typing import Any

import pytest

from uipath.core.guardrails import (
    AllFieldsSelector,
    ApplyTo,
    BooleanRule,
    DeterministicGuardrail,
    DeterministicGuardrailsService,
    FieldReference,
    FieldSource,
    GuardrailScope,
    GuardrailSelector,
    GuardrailValidationResultType,
    NumberRule,
    SpecificFieldsSelector,
    UniversalRule,
    WordRule,
)


@pytest.fixture
def service() -> DeterministicGuardrailsService:
    return DeterministicGuardrailsService()


class TestDeterministicGuardrailsService:
    """Test GuardrailsService functionality."""

    def test_evaluate_post_deterministic_guardrail_validation_passed(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test deterministic guardrail validation with passing rules."""
        # Create a deterministic guardrail matching the C# example
        deterministic_guardrail = DeterministicGuardrail(
            id="test-deterministic-id",
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
                        fields=[FieldReference(path="age", source=FieldSource.INPUT)],
                    ),
                    detects_violation=lambda n: n < 21.0,
                ),
                BooleanRule(
                    rule_type="boolean",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="isActive", source=FieldSource.INPUT)
                        ],
                    ),
                    detects_violation=lambda b: b is not True,
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

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=deterministic_guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED
        assert result.reason == "No rules to apply for output data."

    def test_evaluate_post_deterministic_guardrail_validation_passes_when_input_data_dont_violates_all_the_rules(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test deterministic guardrail validation fails when age is too low."""
        deterministic_guardrail = DeterministicGuardrail(
            id="test-deterministic-id",
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
                        fields=[FieldReference(path="age", source=FieldSource.INPUT)],
                    ),
                    detects_violation=lambda n: n < 21.0,
                ),
                BooleanRule(
                    rule_type="boolean",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="isActive", source=FieldSource.INPUT)
                        ],
                    ),
                    detects_violation=lambda b: b is not True,
                ),
                NumberRule(
                    rule_type="number",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="status", source=FieldSource.OUTPUT)
                        ],
                    ),
                    detects_violation=lambda n: n != 200.0,
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

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=deterministic_guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED
        assert (
            result.reason
            == "Input data didn't match the guardrail condition: [isActive] comparing function [(b): b is not True]"
        )

    def test_evaluate_post_deterministic_guardrail_validation_passes_when_input_and_output_data_dont_violates_all_the_rules(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test deterministic guardrail validation fails when isActive is False."""
        deterministic_guardrail = DeterministicGuardrail(
            id="test-deterministic-id",
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
                        fields=[FieldReference(path="age", source=FieldSource.INPUT)],
                    ),
                    detects_violation=lambda n: n < 21.0,
                ),
                BooleanRule(
                    rule_type="boolean",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="isActive", source=FieldSource.INPUT)
                        ],
                    ),
                    detects_violation=lambda b: b is not True,
                ),
                NumberRule(
                    rule_type="number",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="status", source=FieldSource.OUTPUT)
                        ],
                    ),
                    detects_violation=lambda n: n != 200.0,
                ),
            ],
        )

        # Input data with isActive = False
        input_data = {
            "userName": "John",
            "age": 25,
            "isActive": False,
        }
        output_data = {
            "status": 200,
        }

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=deterministic_guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED
        assert (
            result.reason
            == "Input data didn't match the guardrail condition: [age] comparing function [(n): n < 21.0]"
        )

    def test_evaluate_post_deterministic_guardrail_uses_rule_description(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Ensure rule_description is returned when a rule fails validation."""
        friendly_description = "Username must include 'te' and a digit"
        deterministic_guardrail = DeterministicGuardrail(
            id="test-rule-desc-id",
            name="Regex Guardrail With Description",
            description="Test regex guardrail with description",
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
                            FieldReference(path="userName", source=FieldSource.INPUT)
                        ],
                    ),
                    rule_description=friendly_description,
                    detects_violation=lambda s: not bool(re.search(".*te.*3.*", s)),
                ),
            ],
        )

        # Input data with userName that doesn't match the regex pattern
        input_data = {
            "userName": "test",
        }

        result = service.evaluate_pre_deterministic_guardrail(
            input_data=input_data,
            guardrail=deterministic_guardrail,
        )

        assert result.result == GuardrailValidationResultType.VALIDATION_FAILED
        assert (
            result.reason
            == "Data matched all guardrail conditions: [Username must include 'te' and a digit]"
        )

    def test_evaluate_post_deterministic_guardrail_passes_validation_when_no_output_rules(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test deterministic guardrail validation passes when regex matches."""
        deterministic_guardrail = DeterministicGuardrail(
            id="test-deterministic-id",
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
                            FieldReference(path="userName", source=FieldSource.INPUT)
                        ],
                    ),
                    detects_violation=lambda s: not bool(re.search(".*te.*3.*", s)),
                ),
            ],
        )

        # Input data with userName that matches the regex pattern
        input_data = {
            "userName": "test123",
        }
        output_data: dict[str, Any] = {}

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=deterministic_guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED
        assert result.reason == "No rules to apply for output data."

    def test_evaluate_post_deterministic_guardrail_failes_validation_when_data_macthes_rules(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test deterministic guardrail validation fails when regex doesn't match."""
        deterministic_guardrail = DeterministicGuardrail(
            id="test-deterministic-id",
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
                            FieldReference(path="userName", source=FieldSource.INPUT)
                        ],
                    ),
                    detects_violation=lambda s: not bool(re.search(".*te.*3.*", s)),
                ),
                NumberRule(
                    rule_type="number",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="status", source=FieldSource.OUTPUT)
                        ],
                    ),
                    detects_violation=lambda n: n != 200.0,
                ),
            ],
        )

        # Input data with userName that doesn't match the regex pattern
        input_data = {
            "userName": "test",
        }
        output_data = {
            "status": 201,
        }

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=deterministic_guardrail,
        )

        expected_reason = (
            "Data matched all guardrail conditions: [[userName] comparing function "
            '[(s): not bool(re.search(".*te.*3.*", s))], '
            "[status] comparing function [(n): n != 200.0]]"
        )

        assert result.result == GuardrailValidationResultType.VALIDATION_FAILED
        assert result.reason == expected_reason

    def test_evaluate_post_deterministic_guardrail_word_contains_substring_detects_violation(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test deterministic guardrail validation fails when string contains forbidden substring."""
        deterministic_guardrail = DeterministicGuardrail(
            id="test-deterministic-id",
            name="Word Contains Guardrail",
            description="Test word contains guardrail",
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
                            FieldReference(path="userName", source=FieldSource.INPUT)
                        ],
                    ),
                    detects_violation=lambda s: "dre" in s,
                ),
                NumberRule(
                    rule_type="number",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="status", source=FieldSource.OUTPUT)
                        ],
                    ),
                    detects_violation=lambda n: n != 200.0,
                ),
            ],
        )

        # Input data with userName that contains "dre" - should fail
        input_data = {
            "userName": "andrei",
        }
        output_data = {
            "status": 201,
        }

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=deterministic_guardrail,
        )

        assert result.result == GuardrailValidationResultType.VALIDATION_FAILED
        assert (
            result.reason
            == "Data matched all guardrail conditions: [[userName] comparing function "
            '[(s): "dre" in s], [status] comparing function [(n): n != 200.0]]'
        )

    def test_evaluate_post_deterministic_guardrail_number_func_passes_when_no_input_rules(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test deterministic guardrail validation passes when number func returns True."""
        deterministic_guardrail = DeterministicGuardrail(
            id="test-deterministic-id",
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
                        fields=[FieldReference(path="age", source=FieldSource.INPUT)],
                    ),
                    detects_violation=lambda n: n < 18 or n > 65,
                ),
            ],
        )

        # Input data with age that passes the function check
        input_data = {
            "age": 25,
        }
        output_data: dict[str, Any] = {}

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=deterministic_guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED
        assert result.reason == "No rules to apply for output data."

    def test_evaluate_post_deterministic_guardrail_number_func_negative(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test deterministic guardrail validation fails when number func returns False."""
        deterministic_guardrail = DeterministicGuardrail(
            id="test-deterministic-id",
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
                        fields=[FieldReference(path="age", source=FieldSource.INPUT)],
                    ),
                    detects_violation=lambda n: n < 18 or n > 65,
                ),
                NumberRule(
                    rule_type="number",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="status", source=FieldSource.OUTPUT)
                        ],
                    ),
                    detects_violation=lambda n: n != 200.0,
                ),
            ],
        )

        # Input data with age that fails the function check
        input_data = {
            "age": 70,
        }
        output_data = {
            "status": 201,
        }

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=deterministic_guardrail,
        )

        assert result.result == GuardrailValidationResultType.VALIDATION_FAILED

    def test_evaluate_post_execution_pases_when_only_some_rules_not_met(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test post-execution guardrail passes when only some rules are not met."""
        guardrail = self._create_guardrail_for_pre_execution()
        input_data = {
            "userName": "John",
            "age": 18,  # Less than 21
            "isActive": True,
        }
        output_data = {
            "status": 200,
        }

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED

    def test_should_ignore_post_execution_guardrail_for_pre_execution_returns_false(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test that pre-execution guardrail ignores post-execution data."""
        guardrail = self._create_guardrail_for_post_execution()
        input_data = {
            "userName": "John",
            "age": 25,
            "isActive": True,
        }
        output_data: dict[str, Any] = {}

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        # Should fail because post-execution guardrail needs output data
        assert result.result == GuardrailValidationResultType.PASSED

    def test_should_trigger_policy_post_execution_guardrail_for_pre_execution_returns_false(
        self,
        service: DeterministicGuardrailsService,
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

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        # Pre-execution guardrail should still pass in post-execution
        assert result.result == GuardrailValidationResultType.PASSED

    def test_should_trigger_policy_post_execution_with_output_fields_when_no_violation_then_returns_true(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
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

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED

    def test_post_execution_with_output_fields_when_only_input_conditions_violated_then_returns_true(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
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

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED

    def test_post_execution_with_input_and_output_fields_output_when_only_output_conditions_violated_then_returns_true(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
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

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED

    def test_post_execution_multiple_rules_when_all_conditions_when_no_condition_is_violated_then_returns_true(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
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

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED

    def test_post_execution_rule_with_multiple_conditions_when_no_condition_is_violated_then_returns_true(
        self,
        service: DeterministicGuardrailsService,
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

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED

    def test_post_execution_rule_with_multiple_conditions_when_only_some_conditions_are_violated_then_returns_true(
        self,
        service: DeterministicGuardrailsService,
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

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED

    def test_post_execution_rule_with_multiple_conditions_when_all_condition_are_violated_then_returns_false(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test guardrail with multiple conditions fails when one condition is not met."""
        guardrail = self._create_guardrail_with_rule_having_multiple_conditions()
        input_data = {
            "userName": "John",
            "age": 15,  # < 18
            "isActive": False,  # Not True
        }
        output_data = {
            "result": "Success",
            "status": 201,  # Not 200
            "success": True,
        }

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.VALIDATION_FAILED

    def test_post_execution_with_all_fields_selector_when_no_field_violates_condition_then_returns_true(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test guardrail with AllFieldsSelector passes when output has matching fields."""
        guardrail = DeterministicGuardrail(
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
                    field_selector=AllFieldsSelector(
                        selector_type="all", sources=[FieldSource.OUTPUT]
                    ),
                    detects_violation=lambda n: n != 25.0,
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
            "status": 25,  # Doesn't match the rule value
            "success": True,
        }

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED

    def test_post_execution_with_all_fields_selector_when_all_fields_violate_condition_then_returns_false(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        guardrail = DeterministicGuardrail(
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
                    field_selector=AllFieldsSelector(
                        selector_type="all", sources=[FieldSource.OUTPUT]
                    ),
                    detects_violation=lambda n: n != 25.0,
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
            "status": 20,  # Matches the rule value
            "success": True,
        }

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.VALIDATION_FAILED

    def test_post_execution_with_all_fields_selector_when_empty_output_schema_then_returns_true(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test guardrail with AllFieldsSelector fails when output is empty."""
        guardrail = DeterministicGuardrail(
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
                    field_selector=AllFieldsSelector(
                        selector_type="all", sources=[FieldSource.INPUT]
                    ),
                    detects_violation=lambda n: n != 200.0,
                ),
            ],
        )

        input_data = {
            "userName": "John",
            "age": 25,
            "isActive": True,
        }
        output_data: dict[str, Any] = {}  # Empty output

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED

    def test_should_trigger_policy_pre_execution_always_rule_with_input_apply_to_returns_true(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test UniversalRule with INPUT ApplyTo triggers in pre-execution."""
        guardrail = self._create_guardrail_with_always_rule(ApplyTo.INPUT)
        input_data = {
            "userName": "John",
            "age": 25,
            "isActive": True,
        }

        result = service.evaluate_pre_deterministic_guardrail(
            input_data=input_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.VALIDATION_FAILED
        assert result.reason == "Always rule enforced"

    def test_should_trigger_policy_pre_execution_always_rule_with_output_apply_to_returns_true(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test UniversalRule with OUTPUT ApplyTo does not trigger in pre-execution."""
        guardrail = self._create_guardrail_with_always_rule(ApplyTo.OUTPUT)
        input_data = {
            "userName": "John",
            "age": 25,
            "isActive": True,
        }
        output_data: dict[str, Any] = {}

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED
        assert result.reason == "No rules to apply for input data"

    def test_should_trigger_policy_pre_execution_always_rule_with_input_and_output_apply_to_returns_true(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test UniversalRule with INPUT_AND_OUTPUT ApplyTo triggers in pre-execution."""
        guardrail = self._create_guardrail_with_always_rule(ApplyTo.INPUT_AND_OUTPUT)
        input_data = {
            "userName": "John",
            "age": 25,
            "isActive": True,
        }
        output_data: dict[str, Any] = {}

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.VALIDATION_FAILED
        assert result.reason == "Always rule enforced"

    def test_should_trigger_policy_post_execution_always_rule_with_input_apply_to_returns_false(
        self,
        service: DeterministicGuardrailsService,
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

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED
        assert result.reason == "No rules to apply for output data."

    def test_should_trigger_policy_post_execution_always_rule_with_output_apply_to_returns_true(
        self,
        service: DeterministicGuardrailsService,
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

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.VALIDATION_FAILED
        assert result.reason == "Always rule enforced"

    def test_should_trigger_policy_post_execution_always_rule_with_input_and_output_apply_to_returns_true(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test UniversalRule with INPUT_AND_OUTPUT ApplyTo triggers in post-execution."""
        guardrail = self._create_guardrail_with_always_rule(ApplyTo.INPUT_AND_OUTPUT)
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

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

        assert result.result == GuardrailValidationResultType.VALIDATION_FAILED
        assert result.reason == "Always rule enforced"

        # Helper methods to create guardrails

    def _create_guardrail_for_pre_execution(self) -> DeterministicGuardrail:
        """Create a guardrail for pre-execution testing."""
        return DeterministicGuardrail(
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
                        fields=[FieldReference(path="age", source=FieldSource.INPUT)],
                    ),
                    detects_violation=lambda n: n < 21.0,
                ),
                BooleanRule(
                    rule_type="boolean",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="isActive", source=FieldSource.INPUT)
                        ],
                    ),
                    detects_violation=lambda b: b is not True,
                ),
                NumberRule(
                    rule_type="number",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="status", source=FieldSource.OUTPUT)
                        ],
                    ),
                    detects_violation=lambda n: n != 200.0,
                ),
            ],
        )

    def _create_guardrail_for_post_execution(self) -> DeterministicGuardrail:
        """Create a guardrail for post-execution testing."""
        return DeterministicGuardrail(
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
                        fields=[FieldReference(path="age", source=FieldSource.INPUT)],
                    ),
                    detects_violation=lambda n: n < 21.0,
                ),
                NumberRule(
                    rule_type="number",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="status", source=FieldSource.OUTPUT)
                        ],
                    ),
                    detects_violation=lambda n: n != 200.0,
                ),
            ],
        )

    def _create_guardrail_with_multiple_rules(self) -> DeterministicGuardrail:
        """Create a guardrail with multiple rules."""
        return DeterministicGuardrail(
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
                        fields=[FieldReference(path="age", source=FieldSource.INPUT)],
                    ),
                    detects_violation=lambda n: n < 21.0,
                ),
                BooleanRule(
                    rule_type="boolean",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="isActive", source=FieldSource.INPUT)
                        ],
                    ),
                    detects_violation=lambda b: b is not True,
                ),
                NumberRule(
                    rule_type="number",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="status", source=FieldSource.OUTPUT)
                        ],
                    ),
                    detects_violation=lambda n: n != 200.0,
                ),
            ],
        )

    def _create_guardrail_with_rule_having_multiple_conditions(
        self,
    ) -> DeterministicGuardrail:
        """Create a guardrail with rule having multiple conditions."""
        return DeterministicGuardrail(
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
                        fields=[FieldReference(path="age", source=FieldSource.INPUT)],
                    ),
                    detects_violation=lambda n: n < 21.0,
                ),
                BooleanRule(
                    rule_type="boolean",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="isActive", source=FieldSource.INPUT)
                        ],
                    ),
                    detects_violation=lambda b: b is not True,
                ),
                NumberRule(
                    rule_type="number",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="status", source=FieldSource.OUTPUT)
                        ],
                    ),
                    detects_violation=lambda n: n != 200.0,
                ),
            ],
        )

    def test_evaluate_post_deterministic_guardrail_word_contains_operator_passes(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test deterministic guardrail with word contains operator passes for pre-execution."""
        deterministic_guardrail = DeterministicGuardrail(
            id="b4283bd4-5ce0-49de-a918-2604d830460c",
            name="Before",
            description="",
            enabled_for_evals=True,
            guardrail_type="custom",
            selector=GuardrailSelector(
                scopes=[GuardrailScope.TOOL], match_names=["ConverterToStringAgent"]
            ),
            rules=[
                WordRule(
                    rule_type="word",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(
                                path="input_string", source=FieldSource.INPUT
                            )
                        ],
                    ),
                    detects_violation=lambda s: "cti" in s,
                ),
            ],
        )

        # Input data without "cti" in input_string - should pass
        input_data = {
            "input_string": "test value",
        }
        output_data: dict[str, Any] = {}

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=deterministic_guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED
        assert result.reason == "No rules to apply for output data."

    def test_evaluate_post_deterministic_guardrail_only_output_rules_passes(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test post guardrail with only output rules passes when conditions are met."""
        deterministic_guardrail = DeterministicGuardrail(
            id="test-only-output-id",
            name="Output Only Guardrail",
            description="Test guardrail with only output rules",
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
                            FieldReference(path="status", source=FieldSource.OUTPUT)
                        ],
                    ),
                    detects_violation=lambda n: n != 200.0,
                ),
                WordRule(
                    rule_type="word",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="result", source=FieldSource.OUTPUT)
                        ],
                    ),
                    detects_violation=lambda s: s != "Success",
                ),
            ],
        )

        input_data = {
            "userName": "John",
        }
        output_data = {
            "status": 200,
            "result": "Success",
        }

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=deterministic_guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED
        assert (
            result.reason
            == "Output data didn't match the guardrail condition: [status] comparing function [(n): n != 200.0]"
        )

    def test_evaluate_post_deterministic_guardrail_only_always_rule_fails(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test post guardrail with only UniversalRule always fails."""
        deterministic_guardrail = DeterministicGuardrail(
            id="test-only-always-id",
            name="Always Rule Only Guardrail",
            description="Test guardrail with only always rule",
            enabled_for_evals=True,
            guardrail_type="custom",
            selector=GuardrailSelector(
                scopes=[GuardrailScope.TOOL], match_names=["test"]
            ),
            rules=[
                UniversalRule(
                    rule_type="always",
                    apply_to=ApplyTo.OUTPUT,
                ),
            ],
        )

        input_data = {
            "userName": "John",
        }
        output_data = {
            "status": 200,
        }

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=deterministic_guardrail,
        )

        assert result.result == GuardrailValidationResultType.VALIDATION_FAILED
        assert result.reason == "Always rule enforced"

    def test_evaluate_post_deterministic_guardrail_only_input_rules_passes(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test post guardrail passes when only input rules exist (no output data required)."""
        deterministic_guardrail = DeterministicGuardrail(
            id="test-only-input-id",
            name="Input Only Guardrail",
            description="Test guardrail with only input rules",
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
                        fields=[FieldReference(path="age", source=FieldSource.INPUT)],
                    ),
                    detects_violation=lambda n: n < 18,
                ),
                WordRule(
                    rule_type="word",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[FieldReference(path="name", source=FieldSource.INPUT)],
                    ),
                    detects_violation=lambda s: len(s) < 2,
                ),
            ],
        )

        input_data = {
            "age": 25,
            "name": "John",
        }
        output_data: dict[str, Any] = {}

        result = service.evaluate_post_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=deterministic_guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED
        assert result.reason == "No rules to apply for output data."

    def test_evaluate_pre_deterministic_guardrail_with_input_and_output_rules_input_true(
        self,
        service: DeterministicGuardrailsService,
    ) -> None:
        """Test pre-execution guardrail with input rule and output rules, should pass because is ignored."""
        deterministic_guardrail = DeterministicGuardrail(
            id="test-pre-mixed-rules-id",
            name="Pre Execution Mixed Rules Guardrail",
            description="Test pre-execution with both input and output rules",
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
                        fields=[FieldReference(path="age", source=FieldSource.INPUT)],
                    ),
                    detects_violation=lambda n: n < 21.0,
                ),
                BooleanRule(
                    rule_type="boolean",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="isActive", source=FieldSource.INPUT)
                        ],
                    ),
                    detects_violation=lambda b: b is not True,
                ),
                # Output rule - should be ignored in pre-execution
                NumberRule(
                    rule_type="number",
                    field_selector=SpecificFieldsSelector(
                        selector_type="specific",
                        fields=[
                            FieldReference(path="status", source=FieldSource.OUTPUT)
                        ],
                    ),
                    detects_violation=lambda n: n != 200.0,
                ),
            ],
        )

        input_data = {
            "userName": "John",
            "age": 18,
            "isActive": True,
        }

        result = service.evaluate_pre_deterministic_guardrail(
            input_data=input_data,
            guardrail=deterministic_guardrail,
        )

        assert result.result == GuardrailValidationResultType.PASSED

    def _create_guardrail_with_always_rule(
        self, apply_to: ApplyTo
    ) -> DeterministicGuardrail:
        """Create a guardrail with an AlwaysRule (UniversalRule)."""
        return DeterministicGuardrail(
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
