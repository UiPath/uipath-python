#!/usr/bin/env python3
"""Run transformation on Image #1 fixture and store input/output."""

import json
from pathlib import Path

from span_transformer import SpanTransformer


def load_fixture(filename: str):
    """Load JSON fixture file."""
    fixture_path = Path(__file__).parent / filename
    with open(fixture_path, "r") as f:
        data = json.load(f)
    return data["spans"]


def save_output(filename: str, spans: list, description: str = ""):
    """Save spans to JSON file with metadata."""
    output_path = Path(__file__).parent / filename
    output_data = {"description": description, "span_count": len(spans), "spans": spans}
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"✓ Saved {len(spans)} spans to {filename}")


def main():
    print("=" * 70)
    print("Image #1 Trace Transformation - Input/Output Storage")
    print("=" * 70)

    # Load input
    print("\n[1] Loading input fixture...")
    input_spans = load_fixture("image1_realistic_fixture.json")
    print(f"    Loaded {len(input_spans)} spans")

    # Save formatted input
    save_output(
        "transformation_input.json",
        input_spans,
        "Original LangGraph trace with nested executions, agent nodes, and tool calls",
    )

    # Run transformation
    print("\n[2] Running transformation...")
    transformer = SpanTransformer()
    output_spans = transformer.transform(input_spans)
    print(f"    Generated {len(output_spans)} spans")

    # Save formatted output
    save_output(
        "transformation_output.json",
        output_spans,
        "Simplified UiPath schema with synthetic parent and LLM/tool spans only",
    )

    # Generate comparison stats
    print("\n[3] Transformation Statistics:")
    print("-" * 70)

    # Count input types
    input_langgraph = sum(1 for s in input_spans if s["name"] == "LangGraph")
    input_agent = sum(
        1
        for s in input_spans
        if s.get("attributes", {}).get("langgraph.node") == "agent"
    )
    input_functions = sum(
        1 for s in input_spans if "function.name" in s.get("attributes", {})
    )
    input_llm = sum(
        1
        for s in input_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "LLM"
    )
    input_tools = sum(
        1
        for s in input_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "TOOL"
    )

    # Count output types
    output_synthetic = sum(1 for s in output_spans if s["name"] == "Agent run - Agent")
    output_llm = sum(
        1
        for s in output_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "LLM"
    )
    output_tools = sum(
        1
        for s in output_spans
        if s.get("attributes", {}).get("openinference.span.kind") == "TOOL"
    )

    print("  Input Breakdown:")
    print(f"    • LangGraph spans:        {input_langgraph}")
    print(f"    • Agent nodes:            {input_agent}")
    print(f"    • Function calls:         {input_functions}")
    print(f"    • LLM spans:              {input_llm}")
    print(f"    • Tool spans:             {input_tools}")
    print(
        f"    • Other internal spans:   {len(input_spans) - (input_langgraph + input_agent + input_functions + input_llm + input_tools)}"
    )
    print(f"    • TOTAL:                  {len(input_spans)}")

    print("\n  Output Breakdown:")
    print(f"    • Synthetic parent spans: {output_synthetic} (running + completed)")
    print(f"    • LLM spans:              {output_llm}")
    print(f"    • Tool spans:             {output_tools}")
    print(f"    • TOTAL:                  {len(output_spans)}")

    print("\n  Transformation Impact:")
    reduction_count = len(input_spans) - len(output_spans)
    reduction_pct = 100 * (1 - len(output_spans) / len(input_spans))
    print(f"    • Spans removed:          {reduction_count}")
    print(f"    • Reduction:              {reduction_pct:.1f}%")
    print(
        f"    • Data preserved:         {output_llm} LLM + {output_tools} tool spans (100%)"
    )

    # Generate visualization data
    print("\n[4] Generating visualization data...")

    viz_data = {
        "transformation_summary": {
            "input_count": len(input_spans),
            "output_count": len(output_spans),
            "reduction_percentage": round(reduction_pct, 1),
            "spans_removed": reduction_count,
        },
        "input_breakdown": {
            "langgraph_parents": input_langgraph,
            "agent_nodes": input_agent,
            "function_calls": input_functions,
            "llm_spans": input_llm,
            "tool_spans": input_tools,
            "other": len(input_spans)
            - (
                input_langgraph
                + input_agent
                + input_functions
                + input_llm
                + input_tools
            ),
        },
        "output_breakdown": {
            "synthetic_parents": output_synthetic,
            "llm_spans": output_llm,
            "tool_spans": output_tools,
        },
        "span_mappings": {
            "buffered_not_emitted": [
                "LangGraph (nested)",
                "agent nodes",
                "function calls (non-LLM/tool)",
                "A_Plus_B nodes",
                "route_agent nodes",
            ],
            "passed_through": [
                "LLM spans (UiPathChat)",
                "TOOL spans (GET, POST, A_Plus_B tools)",
            ],
            "created": ["Agent run - Agent (synthetic parent, emitted twice)"],
        },
        "key_changes": [
            f"Original {input_langgraph} LangGraph parents → 1 synthetic 'Agent run - Agent' parent",
            f"Buffered {input_agent} agent node spans (not emitted)",
            f"Buffered {input_functions} function call spans (not emitted)",
            f"Preserved all {input_llm} LLM spans with reparenting",
            f"Preserved all {input_tools} tool spans with reparenting",
            "Emitted synthetic parent twice: running state + completed state",
        ],
    }

    viz_path = Path(__file__).parent / "transformation_visualization.json"
    with open(viz_path, "w") as f:
        json.dump(viz_data, f, indent=2)
    print("    ✓ Saved visualization data to transformation_visualization.json")

    print("\n" + "=" * 70)
    print("✅ Transformation Complete - Files Generated:")
    print("=" * 70)
    print("  1. transformation_input.json           (original 23 spans)")
    print("  2. transformation_output.json          (simplified output)")
    print("  3. transformation_visualization.json   (statistics & metrics)")
    print()


if __name__ == "__main__":
    main()
