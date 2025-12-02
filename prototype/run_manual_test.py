#!/usr/bin/env python3
"""Manual test runner to validate span transformation."""

import json
from pathlib import Path

from span_transformer import SpanTransformer


def load_fixture(filename: str):
    """Load JSON fixture file."""
    fixture_path = Path(__file__).parent / filename
    with open(fixture_path, "r") as f:
        data = json.load(f)
    return data["spans"]


def main():
    print("=" * 60)
    print("Phase 0 Prototype - Manual Test Validation")
    print("=" * 60)

    transformer = SpanTransformer()
    input_spans = load_fixture("langgraph_fixture.json")

    print(f"\n✓ Loaded {len(input_spans)} input spans")

    output_spans = transformer.transform(input_spans)

    print(f"✓ Transformed to {len(output_spans)} output spans")

    # Test 1: Verify span count reduction
    print("\n[Test 1] Span count reduction")
    print(f"  Input spans: {len(input_spans)}")
    print(f"  Output spans: {len(output_spans)}")
    assert len(input_spans) >= 20, "Should have 20+ input spans"
    assert len(output_spans) <= 10, "Should have <=10 output spans"
    print("  ✅ PASS")

    # Test 2: Verify synthetic parent exists
    print("\n[Test 2] Synthetic parent creation")
    synthetic_spans = [s for s in output_spans if s["name"] == "Agent run - Agent"]
    print(f"  Synthetic spans found: {len(synthetic_spans)}")
    assert len(synthetic_spans) == 2, (
        "Should have 2 synthetic spans (running + completed)"
    )
    print("  ✅ PASS")

    # Test 3: Verify progressive states
    print("\n[Test 3] Progressive state emission")
    running_span = synthetic_spans[0]
    completed_span = synthetic_spans[1]
    print(
        f"  Running span status: {running_span['status']} (end_time: {running_span['end_time']})"
    )
    print(
        f"  Completed span status: {completed_span['status']} (end_time: {completed_span['end_time']})"
    )
    assert running_span["status"] == 0, "Running span should have status=0"
    assert running_span["end_time"] is None, "Running span should have end_time=None"
    assert completed_span["status"] == 1, "Completed span should have status=1"
    assert completed_span["end_time"] is not None, (
        "Completed span should have end_time set"
    )
    print("  ✅ PASS")

    # Test 4: Verify LLM/tool spans preserved
    print("\n[Test 4] LLM/tool span preservation")
    input_llm_count = sum(
        1
        for s in input_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "LLM"
    )
    output_llm_count = sum(
        1
        for s in output_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "LLM"
    )
    input_tool_count = sum(
        1
        for s in input_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "TOOL"
    )
    output_tool_count = sum(
        1
        for s in output_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "TOOL"
    )
    print(
        f"  Input LLM spans: {input_llm_count} -> Output LLM spans: {output_llm_count}"
    )
    print(
        f"  Input tool spans: {input_tool_count} -> Output tool spans: {output_tool_count}"
    )
    assert input_llm_count == output_llm_count, "All LLM spans should be preserved"
    assert input_tool_count == output_tool_count, "All tool spans should be preserved"
    print("  ✅ PASS")

    # Test 5: Verify node spans buffered
    print("\n[Test 5] Node span buffering")
    node_spans = [s for s in output_spans if s["name"] in ["agent", "action"]]
    action_prefixed = [s for s in output_spans if s["name"].startswith("action:")]
    print(f"  Node spans in output: {len(node_spans)}")
    print(f"  Action-prefixed spans in output: {len(action_prefixed)}")
    assert len(node_spans) == 0, "No node spans should be in output"
    assert len(action_prefixed) == 0, "No action:* spans should be in output"
    print("  ✅ PASS")

    # Test 6: Verify parent-child hierarchy
    print("\n[Test 6] Parent-child hierarchy")
    synthetic_id = output_spans[0]["id"]
    non_synthetic_spans = [s for s in output_spans if s["name"] != "Agent run - Agent"]
    print(f"  Synthetic parent ID: {synthetic_id}")
    print(f"  Non-synthetic spans: {len(non_synthetic_spans)}")
    for span in non_synthetic_spans:
        assert span["parent_id"] == synthetic_id, (
            f"Span {span['id']} should have synthetic parent"
        )
    print("  ✅ PASS - All LLM/tool spans are children of synthetic parent")

    # Summary
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)
    print("\nTransformation Summary:")
    print(f"  • Input: {len(input_spans)} spans")
    print(f"  • Output: {len(output_spans)} spans")
    print(
        f"  • Reduction: {len(input_spans) - len(output_spans)} spans ({100 * (1 - len(output_spans) / len(input_spans)):.1f}%)"
    )
    print(f"  • LLM spans: {output_llm_count}")
    print(f"  • Tool spans: {output_tool_count}")
    print("  • Synthetic parents: 2 (running + completed)")


if __name__ == "__main__":
    main()
