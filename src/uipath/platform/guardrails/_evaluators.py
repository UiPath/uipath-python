"""Guardrail rule evaluators.

This module provides functions for evaluating different types of guardrail rules
against input and output data.
"""

from enum import IntEnum
from typing import Any

from uipath.core.guardrails import (
    AllFieldsSelector,
    ApplyTo,
    BooleanRule,
    FieldReference,
    FieldSource,
    NumberRule,
    SpecificFieldsSelector,
    UniversalRule,
    WordRule,
)


class ArrayDepth(IntEnum):
    """Array depth enumeration for path parsing."""

    NONE = 0  # Not an array
    SINGLE = 1  # Single array [*]
    MATRIX = 2  # Matrix [*][*]


def extract_field_value(path: str, data: dict[str, Any]) -> list[Any]:
    """Extract field values from data using dot-notation path.

    Supports array notation with [*] and [*][*] for arrays and matrices.
    If an array is encountered at any point in the path, all elements are checked.
    """
    if not isinstance(data, dict):
        return []

    results: list[Any] = []

    def _parse_path_segment(segment: str) -> tuple[str, ArrayDepth]:
        """Parse a path segment to extract field name and array depth."""
        if "[*][*]" in segment:
            field_name = segment.replace("[*][*]", "")
            return field_name, ArrayDepth.MATRIX
        elif "[*]" in segment:
            field_name = segment.replace("[*]", "")
            return field_name, ArrayDepth.SINGLE
        else:
            return segment, ArrayDepth.NONE

    def _traverse(current: Any, remaining_parts: list[str]) -> None:
        """Recursively traverse the path, handling arrays and matrices."""
        if not remaining_parts:
            # End of path, add current value
            if current is not None:
                if isinstance(current, list):
                    # If current is a list, add all elements
                    results.extend(current)
                else:
                    results.append(current)
            return

        part = remaining_parts[0]
        next_parts = remaining_parts[1:]
        field_name, array_depth = _parse_path_segment(part)

        if isinstance(current, dict):
            if field_name not in current:
                return
            next_value = current.get(field_name)

            if array_depth == ArrayDepth.MATRIX:
                # Matrix [*][*] - expect 2D array
                if isinstance(next_value, list):
                    for row in next_value:
                        if isinstance(row, list):
                            for item in row:
                                _traverse(item, next_parts)
                        else:
                            # Not a 2D array, treat as 1D
                            _traverse(row, next_parts)
            elif array_depth == ArrayDepth.SINGLE:
                # Array [*] - expect 1D array
                if isinstance(next_value, list):
                    for item in next_value:
                        _traverse(item, next_parts)
                else:
                    # Not an array, but path expects one - continue traversal
                    _traverse(next_value, next_parts)
            else:
                # No array notation, continue traversal
                if isinstance(next_value, list):
                    # Array encountered without notation - check all elements
                    for item in next_value:
                        _traverse(item, next_parts)
                else:
                    _traverse(next_value, next_parts)
        elif isinstance(current, list):
            # Current is an array - check all elements
            for item in current:
                _traverse(item, remaining_parts)
        else:
            # Cannot traverse further
            return

    path_parts = path.split(".")
    _traverse(data, path_parts)
    return results


def get_fields_from_selector(
    field_selector: AllFieldsSelector | SpecificFieldsSelector,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
) -> list[tuple[Any, FieldReference]]:
    """Get field values and their references based on the field selector."""
    fields: list[tuple[Any, FieldReference]] = []

    if isinstance(field_selector, AllFieldsSelector):
        # For "all" selector, we need to collect all fields from both input and output
        # This is a simplified implementation - in practice, you might want to
        # recursively collect all nested fields
        for key, value in input_data.items():
            fields.append(
                (
                    value,
                    FieldReference(path=key, source=FieldSource.INPUT),
                )
            )
        for key, value in output_data.items():
            fields.append(
                (
                    value,
                    FieldReference(path=key, source=FieldSource.OUTPUT),
                )
            )
    elif isinstance(field_selector, SpecificFieldsSelector):
        # For specific fields, extract values based on field references
        for field_ref in field_selector.fields:
            # Use FieldSource to determine whether to use input_data or output_data
            if field_ref.source == FieldSource.INPUT:
                data = input_data
            elif field_ref.source == FieldSource.OUTPUT:
                data = output_data
            else:
                # Unknown source, skip this field
                continue
            # Extract values (may return multiple if arrays are in the path)
            values = extract_field_value(field_ref.path, data)
            # Add each value as a separate field reference
            for value in values:
                fields.append((value, field_ref))

    return fields


def format_guardrail_error_message(
    field_ref: FieldReference,
    operator: str,
    expected_value: str | None = None,
) -> str:
    """Format a guardrail error message following the standard pattern."""
    source = "Input" if field_ref.source == FieldSource.INPUT else "Output"
    message = f"{source} data didn't match the guardrail condition: [{field_ref.path}] {operator}"
    if expected_value and expected_value.strip():
        message += f" [{expected_value.strip()}]"
    return message


def evaluate_word_rule(
    rule: WordRule, input_data: dict[str, Any], output_data: dict[str, Any]
) -> tuple[bool, str | None]:
    """Evaluate a word rule against input and output data."""
    fields = get_fields_from_selector(rule.field_selector, input_data, output_data)

    for field_value, field_ref in fields:
        if field_value is None:
            continue

        # Word rules should only be applied to string values
        # Skip non-string values (numbers, booleans, objects, arrays, etc.)
        if not isinstance(field_value, str):
            continue

        field_str = field_value

        # Use the custom function to evaluate the rule
        try:
            passed = rule.func(field_str)
        except Exception:
            # If function raises an exception, treat as failure
            passed = False

        if not passed:
            reason = format_guardrail_error_message(
                field_ref, "comparing function", None
            )
            return False, reason

    return True, "All word rule validations passed"


def evaluate_number_rule(
    rule: NumberRule, input_data: dict[str, Any], output_data: dict[str, Any]
) -> tuple[bool, str | None]:
    """Evaluate a number rule against input and output data."""
    fields = get_fields_from_selector(rule.field_selector, input_data, output_data)

    for field_value, field_ref in fields:
        if field_value is None:
            continue

        # Number rules should only be applied to numeric values
        # Skip non-numeric values (strings, booleans, objects, arrays, etc.)
        # Note: bool is a subclass of int in Python, so we must check for bool first
        if isinstance(field_value, bool) or not isinstance(field_value, (int, float)):
            continue

        field_num = float(field_value)

        # Use the custom function to evaluate the rule
        try:
            passed = rule.func(field_num)
        except Exception:
            # If function raises an exception, treat as failure
            passed = False

        if not passed:
            reason = format_guardrail_error_message(
                field_ref, "comparing function", None
            )
            return False, reason

    return True, "All number rule validations passed"


def evaluate_boolean_rule(
    rule: BooleanRule,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
) -> tuple[bool, str | None]:
    """Evaluate a boolean rule against input and output data."""
    fields = get_fields_from_selector(rule.field_selector, input_data, output_data)

    for field_value, field_ref in fields:
        if field_value is None:
            continue

        # Boolean rules should only be applied to boolean values
        # Skip non-boolean values (strings, numbers, objects, arrays, etc.)
        if not isinstance(field_value, bool):
            continue

        field_bool = field_value

        # Use the custom function to evaluate the rule
        try:
            passed = rule.func(field_bool)
        except Exception:
            # If function raises an exception, treat as failure
            passed = False

        if not passed:
            reason = format_guardrail_error_message(
                field_ref, "comparing function", None
            )
            return False, reason

    return True, "All boolean rule validations passed"


def evaluate_universal_rule(
    rule: UniversalRule,
    output_data: dict[str, Any],
) -> tuple[bool, str | None]:
    """Evaluate a universal rule against input and output data.

    Universal rules trigger based on the apply_to scope and execution phase:
    - Pre-execution (empty output_data):
      - INPUT: triggers (validation_passed = False)
      - OUTPUT: does not trigger (validation_passed = True)
      - INPUT_AND_OUTPUT: triggers (validation_passed = False)
    - Post-execution (output_data has data):
      - INPUT: does not trigger (validation_passed = True)
      - OUTPUT: triggers (validation_passed = False)
      - INPUT_AND_OUTPUT: triggers (validation_passed = False)
    """
    # Determine if this is pre-execution (no output data) or post-execution
    is_pre_execution = not output_data or len(output_data) == 0

    if rule.apply_to == ApplyTo.INPUT:
        # INPUT: triggers in pre-execution, does not trigger in post-execution
        if is_pre_execution:
            return False, "Universal rule validation triggered (pre-execution, input)"
        else:
            return True, "Universal rule validation passed (post-execution, input)"
    elif rule.apply_to == ApplyTo.OUTPUT:
        # OUTPUT: does not trigger in pre-execution, triggers in post-execution
        if is_pre_execution:
            return True, "Universal rule validation passed (pre-execution, output)"
        else:
            return False, "Universal rule validation triggered (post-execution, output)"
    elif rule.apply_to == ApplyTo.INPUT_AND_OUTPUT:
        # INPUT_AND_OUTPUT: triggers in both phases
        return False, "Universal rule validation triggered (input and output)"
    else:
        return False, f"Unknown apply_to value: {rule.apply_to}"
