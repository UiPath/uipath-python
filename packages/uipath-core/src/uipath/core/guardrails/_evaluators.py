"""Guardrail rule evaluators.

This module provides functions for evaluating different types of guardrail rules
against input and output data.
"""

import inspect
from enum import IntEnum
from typing import Any, Callable

from .guardrails import (
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
        # For "all" selector, we need to collect all fields from the specified sources
        # This is a simplified implementation - in practice, you might want to
        # recursively collect all nested fields
        if FieldSource.INPUT in field_selector.sources:
            for key, value in input_data.items():
                fields.append(
                    (
                        value,
                        FieldReference(path=key, source=FieldSource.INPUT),
                    )
                )
        if FieldSource.OUTPUT in field_selector.sources:
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


def format_guardrail_passed_validation_result_message(
    field_ref: FieldReference,
    operator: str | None,
    rule_description: str | None,
) -> str:
    """Format a guardrail validation result message following the standard pattern."""
    source = "Input" if field_ref.source == FieldSource.INPUT else "Output"

    if rule_description:
        return (
            f"{source} data didn't match the guardrail condition for field "
            f"[{field_ref.path}]: {rule_description}"
        )

    return (
        f"{source} data didn't match the guardrail condition: "
        f"[{field_ref.path}] comparing function [{operator}]"
    )


def get_validated_conditions_description(
    field_path: str,
    operator: str | None,
    rule_description: str | None,
) -> str:
    if rule_description:
        return rule_description

    return f"[{field_path}] comparing function [{operator}]"


def evaluate_word_rule(
    rule: WordRule, input_data: dict[str, Any], output_data: dict[str, Any]
) -> tuple[bool, str]:
    """Evaluate a word rule against input and output data."""
    fields = get_fields_from_selector(rule.field_selector, input_data, output_data)
    operator = _humanize_guardrail_func(rule.detects_violation) or "violation check"
    field_paths = ", ".join({field_ref.path for _, field_ref in fields})

    for field_value, field_ref in fields:
        if field_value is None:
            continue

        # Word rules should only be applied to string values
        # Skip non-string values (numbers, booleans, objects, arrays, etc.)
        if not isinstance(field_value, str):
            continue

        field_str = field_value

        # Use the custom function to evaluate the rule
        # If detects_violation returns True, it means the rule was violated (validation fails)
        try:
            violation_detected = rule.detects_violation(field_str)
        except Exception:
            # If function raises an exception, treat as failure
            violation_detected = True

        if not violation_detected:
            reason = format_guardrail_passed_validation_result_message(
                field_ref=field_ref,
                operator=operator,
                rule_description=rule.rule_description,
            )
            return True, reason

    return False, get_validated_conditions_description(
        field_path=field_paths,
        operator=operator,
        rule_description=rule.rule_description,
    )


def evaluate_number_rule(
    rule: NumberRule, input_data: dict[str, Any], output_data: dict[str, Any]
) -> tuple[bool, str]:
    """Evaluate a number rule against input and output data."""
    fields = get_fields_from_selector(rule.field_selector, input_data, output_data)
    operator = _humanize_guardrail_func(rule.detects_violation) or "violation check"
    field_paths = ", ".join({field_ref.path for _, field_ref in fields})
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
        # If detects_violation returns True, it means the rule was violated (validation fails)
        try:
            violation_detected = rule.detects_violation(field_num)
        except Exception:
            # If function raises an exception, treat as failure
            violation_detected = True

        if not violation_detected:
            reason = format_guardrail_passed_validation_result_message(
                field_ref=field_ref,
                operator=operator,
                rule_description=rule.rule_description,
            )
            return True, reason

    return False, get_validated_conditions_description(
        field_path=field_paths,
        operator=operator,
        rule_description=rule.rule_description,
    )


def evaluate_boolean_rule(
    rule: BooleanRule,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
) -> tuple[bool, str]:
    """Evaluate a boolean rule against input and output data."""
    fields = get_fields_from_selector(rule.field_selector, input_data, output_data)
    operator = _humanize_guardrail_func(rule.detects_violation) or "violation check"
    field_paths = ", ".join({field_ref.path for _, field_ref in fields})
    for field_value, field_ref in fields:
        if field_value is None:
            continue

        # Boolean rules should only be applied to boolean values
        # Skip non-boolean values (strings, numbers, objects, arrays, etc.)
        if not isinstance(field_value, bool):
            continue

        field_bool = field_value

        # Use the custom function to evaluate the rule
        # If detects_violation returns True, it means the rule was violated (validation fails)
        try:
            violation_detected = rule.detects_violation(field_bool)
        except Exception:
            # If function raises an exception, treat as failure
            violation_detected = True

        if not violation_detected:
            reason = format_guardrail_passed_validation_result_message(
                field_ref=field_ref,
                operator=operator,
                rule_description=rule.rule_description,
            )
            return True, reason

    return False, get_validated_conditions_description(
        field_path=field_paths,
        operator=operator,
        rule_description=rule.rule_description,
    )


def evaluate_universal_rule(
    rule: UniversalRule,
    output_data: dict[str, Any],
) -> tuple[bool, str]:
    """Evaluate a universal rule against input and output data.

    Universal rules trigger based on the apply_to scope and execution phase:
    - Pre-execution (empty output_data):
      - INPUT: triggers (result = VALIDATION_FAILED)
      - OUTPUT: does not trigger (result = PASSED)
      - INPUT_AND_OUTPUT: triggers (result = VALIDATION_FAILED)
    - Post-execution (output_data has data):
      - INPUT: does not trigger (result = PASSED)
      - OUTPUT: triggers (result = VALIDATION_FAILED)
      - INPUT_AND_OUTPUT: triggers (result = VALIDATION_FAILED)
    """
    # Determine if this is pre-execution (no output data) or post-execution
    is_pre_execution = not output_data or len(output_data) == 0

    if rule.apply_to == ApplyTo.INPUT:
        # INPUT: triggers in pre-execution, does not trigger in post-execution
        if is_pre_execution:
            return False, "Always rule enforced"
        else:
            return True, "No rules to apply for output data"
    elif rule.apply_to == ApplyTo.OUTPUT:
        # OUTPUT: does not trigger in pre-execution, triggers in post-execution
        if is_pre_execution:
            return True, "No rules to apply for input data"
        else:
            return False, "Always rule enforced"
    elif rule.apply_to == ApplyTo.INPUT_AND_OUTPUT:
        # INPUT_AND_OUTPUT: triggers in both phases
        return False, "Always rule enforced"
    else:
        return False, f"Unknown apply_to value: {rule.apply_to}"


def _humanize_guardrail_func(func: Callable[..., Any] | str | None) -> str | None:
    """Build a user-friendly description of a guardrail predicate.

    Deterministic guardrails store Python callables (often lambdas) to evaluate
    conditions. For diagnostics, it's useful to include a readable hint about the
    predicate that failed.

    Args:
        func: A Python callable used as a predicate, or a pre-rendered string
            description (for example, ``"s:str -> bool: contains 'test'"``).

    Returns:
        A human-readable description, or ``None`` if one cannot be produced.
    """
    if func is None:
        return None

    if isinstance(func, str):
        rendered = func.strip()
        return rendered or None

    name = getattr(func, "__name__", None)
    if name and name != "<lambda>":
        return name

    # Best-effort extraction for lambdas / callables.
    try:
        sig = str(inspect.signature(func))
    except (TypeError, ValueError):
        sig = ""

    try:
        source_lines = inspect.getsourcelines(func)
        source = "".join(source_lines[0]).strip()
        # Collapse whitespace to keep the message compact.
        source = " ".join(source.split())

        # Remove "detects_violation=lambda" prefix if present
        # Pattern: "detects_violation=lambda s: condition" -> "condition"
        if "detects_violation=lambda" in source:
            # Find the lambda part
            lambda_start = source.find("detects_violation=lambda")
            if lambda_start != -1:
                # Get everything after "detects_violation=lambda"
                lambda_part = source[
                    lambda_start + len("detects_violation=lambda") :
                ].strip()
                # Find the colon that separates param from body
                colon_idx = lambda_part.find(":")
                if colon_idx != -1:
                    # Extract just the body (condition)
                    body = lambda_part[colon_idx + 1 :].strip()
                    # Remove trailing comma if present
                    body = body.rstrip(",").strip()
                    source = body
    except (OSError, TypeError):
        source = ""

    if source and sig:
        return f"{sig}: {source}"
    if source:
        return source
    if sig:
        return sig

    rendered = repr(func).strip()
    return rendered or None
