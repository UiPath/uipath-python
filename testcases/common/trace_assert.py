"""
Simple trace assertion - just check that expected spans exist with required attributes.
Much simpler than the tree-based approach.
"""

import json
from typing import List, Dict, Any


def load_traces(traces_file: str) -> List[Dict[str, Any]]:
    """Load traces from a JSONL file."""
    traces = []
    with open(traces_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                traces.append(json.loads(line))
    return traces


def load_expected_traces(expected_file: str) -> List[Dict[str, Any]]:
    """Load expected trace definitions from a JSON file."""
    with open(expected_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('required_spans', [])


def get_attributes(span: Dict[str, Any]) -> Dict[str, Any]:
    """Parse attributes from a span."""
    return span.get('attributes', {})


def matches_value(expected_value: Any, actual_value: Any) -> bool:
    """
    Check if an actual value matches the expected value.

    Supports:
    - List of possible values: ["value1", "value2"]
    - Wildcard: "*" (any value accepted)
    - Exact match: "value"
    """
    # Wildcard - accept any value
    if expected_value == "*":
        return True

    # List of possible values
    if isinstance(expected_value, list):
        return actual_value in expected_value

    # Exact match
    return expected_value == actual_value


def matches_expected(span: Dict[str, Any], expected: Dict[str, Any], all_spans: List[Dict[str, Any]] = None) -> bool:
    """Check if a span matches the expected definition."""
    # Check name - can be a string or list of possible names
    expected_name = expected.get('name')
    actual_name = span.get('name')

    if isinstance(expected_name, list):
        if actual_name not in expected_name:
            return False
    elif expected_name != actual_name:
        return False

    # Check span type if specified
    if 'span_type' in expected:
        actual_attrs = get_attributes(span)
        actual_span_type = actual_attrs.get('span_type')

        if actual_span_type != expected['span_type']:
            return False

    # Check parent if specified
    if 'parent' in expected:
        expected_parent = expected['parent']
        actual_parent_id = span.get('parent_id')

        # Handle null parent (root span)
        if expected_parent is None:
            if actual_parent_id is not None:
                return False
        else:
            # Find parent span by name
            if all_spans is None:
                return False

            parent_span = None
            for s in all_spans:
                if s.get('context', {}).get('span_id') == actual_parent_id:
                    parent_span = s
                    break

            if parent_span is None:
                return False

            # Check if parent name matches expected
            parent_name = parent_span.get('name')
            if isinstance(expected_parent, list):
                if parent_name not in expected_parent:
                    return False
            elif parent_name != expected_parent:
                return False

    # Check attributes if specified
    if 'attributes' in expected:
        actual_attrs = get_attributes(span)
        for key, expected_value in expected['attributes'].items():
            if key not in actual_attrs:
                return False
            # Use flexible value matching
            if not matches_value(expected_value, actual_attrs[key]):
                return False

    return True


def assert_traces(traces_file: str, expected_file: str) -> None:
    """
    Assert that all expected traces exist in the traces file.

    Args:
        traces_file: Path to the traces.jsonl file
        expected_file: Path to the expected_traces.json file

    Raises:
        AssertionError: If any expected trace is not found
    """
    traces = load_traces(traces_file)
    expected_spans = load_expected_traces(expected_file)

    print(f"Loaded {len(traces)} traces from {traces_file}")
    print(f"Checking {len(expected_spans)} expected spans...")

    missing_spans = []

    for expected in expected_spans:
        # Find a matching span
        found = False
        for span in traces:
            if matches_expected(span, expected, traces):
                found = True
                print(f"✓ Found span: {expected['name']}")
                break

        if not found:
            missing_spans.append(expected['name'])
            print(f"✗ Missing span: {expected['name']}")

    if missing_spans:
        raise AssertionError(
            f"Missing expected spans: {', '.join(missing_spans)}\n"
            f"Expected {len(expected_spans)} spans, found {len(expected_spans) - len(missing_spans)}"
        )

    print(f"\n✓ All {len(expected_spans)} expected spans found!")


if __name__ == "__main__":
    # Example usage
    assert_traces(".uipath/traces.jsonl", "expected_traces.json")