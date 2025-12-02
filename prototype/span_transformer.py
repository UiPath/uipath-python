import uuid
from typing import Any, Dict, List, Optional


class SpanTransformer:
    """Transforms verbose LangGraph OpenTelemetry spans into simplified UiPath schema."""

    def __init__(self):
        self.buffered_spans: List[Dict[str, Any]] = []
        self.synthetic_span_id: Optional[str] = None

    def transform(self, input_spans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform LangGraph spans to UiPath schema.

        Input: Raw OTEL spans (20+ spans)
        Output: Simplified UiPath spans (5-6 spans)
        """
        output_spans = []
        langgraph_parent = None

        # Pass 1: Identify LangGraph parent and generate synthetic ID
        for span in input_spans:
            if self._is_langgraph_parent(span):
                langgraph_parent = span
                self.synthetic_span_id = f"synthetic-{uuid.uuid4()}"
                break

        if not langgraph_parent:
            # No LangGraph execution found, pass through all spans
            return input_spans

        # Pass 2: Emit "running" state immediately
        running_span = self._create_synthetic_parent(langgraph_parent, is_final=False)
        output_spans.append(running_span)

        # Pass 3: Process all spans
        for span in input_spans:
            if self._is_langgraph_parent(span):
                # Skip original parent (replaced by synthetic)
                continue
            elif self._is_node_span(span):
                # Buffer (don't emit)
                self.buffered_spans.append(span)
            elif self._is_llm_or_tool_span(span):
                # Pass through, but reparent to synthetic span
                output_span = span.copy()
                output_span["parent_id"] = self.synthetic_span_id
                output_spans.append(output_span)

        # Pass 4: Emit "completed" state
        completed_span = self._create_synthetic_parent(langgraph_parent, is_final=True)
        output_spans.append(completed_span)

        return output_spans

    def _is_langgraph_parent(self, span: Dict[str, Any]) -> bool:
        """Check if span is LangGraph root."""
        return span.get("name") == "LangGraph"

    def _is_node_span(self, span: Dict[str, Any]) -> bool:
        """Check if span should be buffered (agent/action)."""
        name = span.get("name", "")
        attributes = span.get("attributes", {})

        return (
            name in ["agent", "action"]
            or name.startswith("action:")
            or "langgraph.node" in attributes
        )

    def _is_llm_or_tool_span(self, span: Dict[str, Any]) -> bool:
        """Check if span should pass through."""
        kind = span.get("attributes", {}).get("openinference.span.kind")
        return kind in ["LLM", "TOOL"]

    def _create_synthetic_parent(
        self, langgraph_span: Dict[str, Any], is_final: bool
    ) -> Dict[str, Any]:
        """Create 'Agent run - Agent' synthetic span."""
        return {
            "id": self.synthetic_span_id,
            "trace_id": langgraph_span["trace_id"],
            "name": "Agent run - Agent",
            "parent_id": None,
            "start_time": langgraph_span["start_time"],
            "end_time": langgraph_span["end_time"] if is_final else None,
            "status": 1 if is_final else 0,  # 0=running, 1=completed
            "attributes": {
                "openinference.span.kind": "CHAIN",
                "langgraph.simplified": True,
            },
        }
