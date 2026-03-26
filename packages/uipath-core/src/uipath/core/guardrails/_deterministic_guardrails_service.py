from typing import Any

from pydantic import BaseModel

from ..tracing.decorators import traced
from ._evaluators import (
    evaluate_boolean_rule,
    evaluate_number_rule,
    evaluate_universal_rule,
    evaluate_word_rule,
)
from .guardrails import (
    AllFieldsSelector,
    ApplyTo,
    BooleanRule,
    DeterministicGuardrail,
    FieldSource,
    GuardrailValidationResult,
    GuardrailValidationResultType,
    NumberRule,
    SpecificFieldsSelector,
    UniversalRule,
    WordRule,
)


class DeterministicGuardrailsService(BaseModel):
    @traced("evaluate_pre_deterministic_guardrail", run_type="uipath")
    def evaluate_pre_deterministic_guardrail(
        self,
        input_data: dict[str, Any],
        guardrail: DeterministicGuardrail,
    ) -> GuardrailValidationResult:
        """Evaluate deterministic guardrail rules against input data (pre-execution)."""
        # Check if guardrail contains any output-dependent rules
        has_output_rule = self._has_output_dependent_rule(guardrail, [ApplyTo.OUTPUT])

        # If guardrail has output-dependent rules, skip evaluation in pre-execution
        # Output rules will be evaluated during post-execution
        if has_output_rule:
            return GuardrailValidationResult(
                result=GuardrailValidationResultType.PASSED,
                reason="No rules to apply for input data.",
            )
        return self._evaluate_deterministic_guardrail(
            input_data=input_data,
            output_data={},
            guardrail=guardrail,
        )

    @traced("evaluate_post_deterministic_guardrails", run_type="uipath")
    def evaluate_post_deterministic_guardrail(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        guardrail: DeterministicGuardrail,
    ) -> GuardrailValidationResult:
        """Evaluate deterministic guardrail rules against input and output data."""
        # Check if guardrail contains any output-dependent rules
        has_output_rule = self._has_output_dependent_rule(
            guardrail, [ApplyTo.OUTPUT, ApplyTo.INPUT_AND_OUTPUT]
        )

        # If guardrail has no output-dependent rules, skip post-execution evaluation
        # Only input rules exist and they should have been evaluated during pre-execution
        if not has_output_rule:
            return GuardrailValidationResult(
                result=GuardrailValidationResultType.PASSED,
                reason="No rules to apply for output data.",
            )

        return self._evaluate_deterministic_guardrail(
            input_data=input_data,
            output_data=output_data,
            guardrail=guardrail,
        )

    @staticmethod
    def _has_output_dependent_rule(
        guardrail: DeterministicGuardrail,
        universal_rules_apply_to_values: list[ApplyTo],
    ) -> bool:
        """Check if at least one rule EXCLUSIVELY requires output data.

        Args:
            guardrail: The guardrail to check
            universal_rules_apply_to_values: List of ApplyTo values to consider as output-dependent for UniversalRules.

        Returns:
            True if at least one rule exclusively depends on output data, False otherwise.
        """
        for rule in guardrail.rules:
            # UniversalRule: only return True if it applies to values in universal_rules_apply_to_values
            if isinstance(rule, UniversalRule):
                if rule.apply_to in universal_rules_apply_to_values:
                    return True
            # Rules with field_selector
            elif isinstance(rule, (WordRule, NumberRule, BooleanRule)):
                field_selector = rule.field_selector
                # AllFieldsSelector applies to both input and output, not exclusively output
                # SpecificFieldsSelector: only return True if at least one field has OUTPUT source
                if isinstance(field_selector, SpecificFieldsSelector):
                    if field_selector.fields and any(
                        field.source == FieldSource.OUTPUT
                        for field in field_selector.fields
                    ):
                        return True
                elif isinstance(field_selector, AllFieldsSelector):
                    if FieldSource.OUTPUT in field_selector.sources:
                        return True

        return False

    @staticmethod
    def _evaluate_deterministic_guardrail(
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        guardrail: DeterministicGuardrail,
    ) -> GuardrailValidationResult:
        """Evaluate deterministic guardrail rules against input and output data.

        Validation fails only if ALL guardrail rules are violated.
        """
        validated_conditions: list[str] = []

        for rule in guardrail.rules:
            if isinstance(rule, WordRule):
                passed, reason = evaluate_word_rule(rule, input_data, output_data)
            elif isinstance(rule, NumberRule):
                passed, reason = evaluate_number_rule(rule, input_data, output_data)
            elif isinstance(rule, BooleanRule):
                passed, reason = evaluate_boolean_rule(rule, input_data, output_data)
            elif isinstance(rule, UniversalRule):
                passed, reason = evaluate_universal_rule(rule, output_data)
            else:
                return GuardrailValidationResult(
                    result=GuardrailValidationResultType.VALIDATION_FAILED,
                    reason=f"Unknown rule type: {type(rule)}",
                )
            validated_conditions.append(reason)
            if passed:
                return GuardrailValidationResult(
                    result=GuardrailValidationResultType.PASSED,
                    reason=reason,
                )

        has_always_rule = any(
            condition == "Always rule enforced" for condition in validated_conditions
        )

        validated_conditions_str = ", ".join(validated_conditions)
        final_reason = (
            "Always rule enforced"
            if has_always_rule
            else f"Data matched all guardrail conditions: [{validated_conditions_str}]"
        )

        return GuardrailValidationResult(
            result=GuardrailValidationResultType.VALIDATION_FAILED,
            reason=final_reason,
        )
