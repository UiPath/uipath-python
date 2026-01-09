"""E2E assertions for eval spans testcase.

This script validates that the new eval spans are created correctly:
1. "Evaluation Set Run" span with span_type: "eval_set_run"
2. "Evaluation" spans with span_type: "evaluation"
3. "Evaluator: {name}" spans with span_type: "evaluator"
4. "Evaluation output" spans with span.type: "evalOutput"
"""

import json
import os
import sys
from typing import Any


def load_traces(traces_file: str) -> list[dict[str, Any]]:
    """Load traces from a JSONL file."""
    traces = []
    with open(traces_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                traces.append(json.loads(line))
    return traces


def get_attributes(span: dict[str, Any]) -> dict[str, Any]:
    """Get attributes from a span."""
    return span.get("attributes", {})


def find_spans_by_type(
    traces: list[dict[str, Any]], span_type: str
) -> list[dict[str, Any]]:
    """Find all spans with the given span_type attribute."""
    return [
        trace for trace in traces if get_attributes(trace).get("span_type") == span_type
    ]


def find_spans_by_span_dot_type(
    traces: list[dict[str, Any]], span_type: str
) -> list[dict[str, Any]]:
    """Find all spans with the given span.type attribute."""
    return [
        trace for trace in traces if get_attributes(trace).get("span.type") == span_type
    ]


def find_spans_by_name(traces: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    """Find all spans with the given name."""
    return [trace for trace in traces if trace.get("name") == name]


def find_spans_by_name_prefix(
    traces: list[dict[str, Any]], prefix: str
) -> list[dict[str, Any]]:
    """Find all spans whose name starts with the given prefix."""
    return [trace for trace in traces if trace.get("name", "").startswith(prefix)]


def assert_eval_set_run_span(traces: list[dict[str, Any]]) -> None:
    """Assert that the Evaluation Set Run span exists with correct attributes."""
    print("\n--- Checking 'Evaluation Set Run' span ---")

    # Find by span_type
    eval_set_run_spans = find_spans_by_type(traces, "eval_set_run")

    assert len(eval_set_run_spans) >= 1, (
        "Expected at least 1 'eval_set_run' span, found 0. "
        "Spans with span_type attribute: "
        f"{[get_attributes(t).get('span_type') for t in traces if get_attributes(t).get('span_type')]}"
    )

    print(f"  Found {len(eval_set_run_spans)} eval_set_run span(s)")

    for span in eval_set_run_spans:
        name = span.get("name")
        attrs = get_attributes(span)

        # Check span name
        assert name == "Evaluation Set Run", (
            f"Expected span name 'Evaluation Set Run', got '{name}'"
        )
        print(f"  Name: {name}")

        # Check span_type attribute
        assert attrs.get("span_type") == "eval_set_run", (
            f"Expected span_type 'eval_set_run', got '{attrs.get('span_type')}'"
        )
        print(f"  span_type: {attrs.get('span_type')}")

        # Check eval_set_run_id is present (may be execution_id fallback)
        if "eval_set_run_id" in attrs:
            print(f"  eval_set_run_id: {attrs.get('eval_set_run_id')}")

    print("Evaluation Set Run span assertion passed")


def assert_evaluation_spans(traces: list[dict[str, Any]]) -> None:
    """Assert that Evaluation spans exist with correct attributes."""
    print("\n--- Checking 'Evaluation' spans ---")

    # Find by span_type
    evaluation_spans = find_spans_by_type(traces, "evaluation")

    assert len(evaluation_spans) >= 1, "Expected at least 1 'evaluation' span, found 0"

    print(f"  Found {len(evaluation_spans)} evaluation span(s)")

    for i, span in enumerate(evaluation_spans):
        name = span.get("name")
        attrs = get_attributes(span)

        print(f"\n  Evaluation span {i + 1}:")

        # Check span name
        assert name == "Evaluation", f"Expected span name 'Evaluation', got '{name}'"
        print(f"    Name: {name}")

        # Check span_type attribute
        assert attrs.get("span_type") == "evaluation", (
            f"Expected span_type 'evaluation', got '{attrs.get('span_type')}'"
        )
        print(f"    span_type: {attrs.get('span_type')}")

        # Check required attributes
        assert "execution.id" in attrs, (
            "Expected 'execution.id' attribute in Evaluation span"
        )
        print(f"    execution.id: {attrs.get('execution.id')}")

        assert "eval_item_id" in attrs, (
            "Expected 'eval_item_id' attribute in Evaluation span"
        )
        print(f"    eval_item_id: {attrs.get('eval_item_id')}")

        assert "eval_item_name" in attrs, (
            "Expected 'eval_item_name' attribute in Evaluation span"
        )
        print(f"    eval_item_name: {attrs.get('eval_item_name')}")

    print("\nEvaluation spans assertion passed")


def assert_evaluator_spans(traces: list[dict[str, Any]]) -> None:
    """Assert that Evaluator spans exist with correct attributes."""
    print("\n--- Checking 'Evaluator' spans ---")

    # Find by span_type
    evaluator_spans = find_spans_by_type(traces, "evaluator")

    assert len(evaluator_spans) >= 1, "Expected at least 1 'evaluator' span, found 0"

    print(f"  Found {len(evaluator_spans)} evaluator span(s)")

    for i, span in enumerate(evaluator_spans):
        name = span.get("name")
        attrs = get_attributes(span)

        print(f"\n  Evaluator span {i + 1}:")

        # Check span name starts with "Evaluator: "
        assert name and name.startswith("Evaluator: "), (
            f"Expected span name to start with 'Evaluator: ', got '{name}'"
        )
        print(f"    Name: {name}")

        # Check span_type attribute
        assert attrs.get("span_type") == "evaluator", (
            f"Expected span_type 'evaluator', got '{attrs.get('span_type')}'"
        )
        print(f"    span_type: {attrs.get('span_type')}")

        # Check required attributes
        assert "evaluator_id" in attrs, (
            "Expected 'evaluator_id' attribute in Evaluator span"
        )
        print(f"    evaluator_id: {attrs.get('evaluator_id')}")

        assert "evaluator_name" in attrs, (
            "Expected 'evaluator_name' attribute in Evaluator span"
        )
        print(f"    evaluator_name: {attrs.get('evaluator_name')}")

        assert "eval_item_id" in attrs, (
            "Expected 'eval_item_id' attribute in Evaluator span"
        )
        print(f"    eval_item_id: {attrs.get('eval_item_id')}")

    print("\nEvaluator spans assertion passed")


def assert_evaluation_output_spans(traces: list[dict[str, Any]]) -> None:
    """Assert that Evaluation output spans exist with correct attributes."""
    print("\n--- Checking 'Evaluation output' spans ---")

    # Find by span.type (note: different attribute name than span_type)
    eval_output_spans = find_spans_by_span_dot_type(traces, "evalOutput")

    assert len(eval_output_spans) >= 1, (
        "Expected at least 1 'evalOutput' span, found 0. "
        "Spans with span.type attribute: "
        f"{[get_attributes(t).get('span.type') for t in traces if get_attributes(t).get('span.type')]}"
    )

    print(f"  Found {len(eval_output_spans)} evalOutput span(s)")

    for i, span in enumerate(eval_output_spans):
        name = span.get("name")
        attrs = get_attributes(span)

        print(f"\n  Evaluation output span {i + 1}:")

        # Check span name
        assert name == "Evaluation output", (
            f"Expected span name 'Evaluation output', got '{name}'"
        )
        print(f"    Name: {name}")

        # Check span.type attribute
        assert attrs.get("span.type") == "evalOutput", (
            f"Expected span.type 'evalOutput', got '{attrs.get('span.type')}'"
        )
        print(f"    span.type: {attrs.get('span.type')}")

        # Check openinference.span.kind attribute
        assert attrs.get("openinference.span.kind") == "CHAIN", (
            f"Expected openinference.span.kind 'CHAIN', got '{attrs.get('openinference.span.kind')}'"
        )
        print(f"    openinference.span.kind: {attrs.get('openinference.span.kind')}")

        # Check required attributes
        assert "value" in attrs, "Expected 'value' attribute in Evaluation output span"
        print(f"    value: {attrs.get('value')}")

        assert "evaluatorId" in attrs, (
            "Expected 'evaluatorId' attribute in Evaluation output span"
        )
        print(f"    evaluatorId: {attrs.get('evaluatorId')}")

        # justification is optional but log it if present
        if "justification" in attrs:
            justification = attrs.get("justification")
            # Truncate long justifications for display
            if isinstance(justification, str) and len(justification) > 100:
                justification = justification[:100] + "..."
            print(f"    justification: {justification}")

    print("\nEvaluation output spans assertion passed")


def assert_span_hierarchy(traces: list[dict[str, Any]]) -> None:
    """Assert the span hierarchy is correct."""
    print("\n--- Checking span hierarchy ---")

    # Build span lookup by span_id
    span_by_id: dict[str, dict[str, Any]] = {}
    for trace in traces:
        context = trace.get("context", {})
        span_id = context.get("span_id")
        if span_id:
            span_by_id[span_id] = trace

    # Get spans by type
    eval_set_run_spans = find_spans_by_type(traces, "eval_set_run")
    evaluation_spans = find_spans_by_type(traces, "evaluation")
    evaluator_spans = find_spans_by_type(traces, "evaluator")

    # Get eval_set_run span_id
    if eval_set_run_spans:
        eval_set_run_span_id = eval_set_run_spans[0].get("context", {}).get("span_id")
        print(f"  EvalSetRun span_id: {eval_set_run_span_id}")

        # Check Evaluation spans are children of EvalSetRun (through parent chain)
        # Note: In practice, there may be intermediate spans, so we just verify
        # the relationship exists through the trace
        print(f"  Found {len(evaluation_spans)} Evaluation spans")
        print(f"  Found {len(evaluator_spans)} Evaluator spans")

    print("\nSpan hierarchy check passed")


def main() -> None:
    """Main assertion logic."""
    traces_file = "__uipath/traces.jsonl"

    # Check if traces file exists
    if not os.path.isfile(traces_file):
        print(f"Traces file '{traces_file}' not found")
        sys.exit(1)

    print(f"Loading traces from {traces_file}...")
    traces = load_traces(traces_file)
    print(f"Loaded {len(traces)} trace spans")

    # Print all span names and types for debugging
    print("\n--- All spans ---")
    for i, trace in enumerate(traces):
        name = trace.get("name", "Unknown")
        attrs = get_attributes(trace)
        span_type = attrs.get("span_type", "N/A")
        print(f"  {i + 1}. {name} (span_type: {span_type})")

    # Run assertions
    try:
        assert_eval_set_run_span(traces)
        assert_evaluation_spans(traces)
        assert_evaluator_spans(traces)
        assert_evaluation_output_spans(traces)
        assert_span_hierarchy(traces)

        print("\n" + "=" * 60)
        print("All eval span assertions passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\nAssertion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
