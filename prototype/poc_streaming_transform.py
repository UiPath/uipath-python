#!/usr/bin/env python3
"""POC: Streaming LangGraph to NotLangGraph transformation.

Simulates streaming input spans and outputs transformed spans progressively.
"""

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

# === SIMULATED STREAMING INPUT (LangGraph spans) ===
# These arrive one at a time, simulating real OTLP streaming

STREAMING_INPUT: List[Dict[str, Any]] = [
    # 1. LangGraph root starts
    {
        "event": "on_start",
        "span": {
            "id": "lg-001",
            "trace_id": "trace-abc",
            "parent_id": None,
            "name": "LangGraph",
            "start_time": 1000,
            "attributes": {},
        },
    },
    # 2. init node (filtered)
    {
        "event": "on_end",
        "span": {
            "id": "lg-002",
            "trace_id": "trace-abc",
            "parent_id": "lg-001",
            "name": "init",
            "start_time": 1001,
            "end_time": 1002,
            "attributes": {"metadata": '{"langgraph_node": "init"}'},
        },
    },
    # 3. agent node (filtered)
    {
        "event": "on_end",
        "span": {
            "id": "lg-003",
            "trace_id": "trace-abc",
            "parent_id": "lg-001",
            "name": "agent",
            "start_time": 1002,
            "end_time": 1010,
            "attributes": {"metadata": '{"langgraph_node": "agent"}'},
        },
    },
    # 4. LLM span (UiPathChat) - this gets transformed
    {
        "event": "on_end",
        "span": {
            "id": "lg-004",
            "trace_id": "trace-abc",
            "parent_id": "lg-003",
            "name": "UiPathChat",
            "start_time": 1003,
            "end_time": 1009,
            "attributes": {
                "openinference.span.kind": "LLM",
                "llm.model_name": "gpt-4o",
                "llm.token_count.prompt": 100,
                "llm.token_count.completion": 50,
                "llm.token_count.total": 150,
                "llm.invocation_parameters": '{"temperature": 0, "max_tokens": 1024}',
            },
        },
    },
    # 5. action node (filtered)
    {
        "event": "on_end",
        "span": {
            "id": "lg-005",
            "trace_id": "trace-abc",
            "parent_id": "lg-001",
            "name": "action:end_execution",
            "start_time": 1010,
            "end_time": 1011,
            "attributes": {},
        },
    },
    # 6. LangGraph root ends
    {
        "event": "on_end",
        "span": {
            "id": "lg-001",
            "trace_id": "trace-abc",
            "parent_id": None,
            "name": "LangGraph",
            "start_time": 1000,
            "end_time": 1012,
            "attributes": {
                "output.value": json.dumps(
                    {
                        "messages": [
                            {"type": "system", "content": "You are an assistant."},
                            {"type": "human", "content": "What is 2+2?"},
                        ],
                        "content": "The answer is 4.",
                    }
                )
            },
        },
    },
]


# === TRANSFORMER STATE ===

LANGGRAPH_NODE_NAMES: Set[str] = {"init", "agent", "action", "route_agent", "terminate"}


@dataclass
class AgentExecution:
    """Tracks state for a single LangGraph execution."""

    trace_id: str
    langgraph_span_id: str
    synthetic_span_id: str
    start_time: Optional[int] = None
    end_time: Optional[int] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    llm_count: int = 0


class StreamingTransformer:
    """Transforms LangGraph spans to NotLangGraph schema progressively."""

    def __init__(self):
        self.executions: Dict[str, AgentExecution] = {}  # trace_id -> execution
        self.output_spans: List[Dict[str, Any]] = []

    def _gen_id(self) -> str:
        return format(uuid.uuid4().int >> 64, "016x")

    def _is_node_span(self, span: Dict) -> bool:
        name = span.get("name", "")
        if name in LANGGRAPH_NODE_NAMES or name.startswith("action:"):
            return True
        attrs = span.get("attributes", {})
        metadata = attrs.get("metadata", "{}")
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except:
                metadata = {}
        return "langgraph_node" in metadata if isinstance(metadata, dict) else False

    def _is_llm_span(self, span: Dict) -> bool:
        attrs = span.get("attributes", {})
        return attrs.get("openinference.span.kind") == "LLM"

    def _emit(self, span: Dict[str, Any]) -> None:
        """Emit a transformed span."""
        self.output_spans.append(span)
        print(f"  EMIT: {span['name']} (id={span['id'][:8]}...)")

    def process_event(self, event: Dict[str, Any]) -> None:
        """Process a single streaming event."""
        event_type = event["event"]
        span = event["span"]
        trace_id = span["trace_id"]
        span_id = span["id"]
        name = span["name"]

        print(f"\n>> {event_type.upper()}: {name} (id={span_id})")

        # ON_START: Detect LangGraph root, emit Agent run immediately
        if event_type == "on_start" and name == "LangGraph":
            synthetic_id = self._gen_id()
            execution = AgentExecution(
                trace_id=trace_id,
                langgraph_span_id=span_id,
                synthetic_span_id=synthetic_id,
                start_time=span["start_time"],
            )
            self.executions[trace_id] = execution

            # Emit "Agent run" in RUNNING state (no end_time)
            self._emit(
                {
                    "id": synthetic_id,
                    "trace_id": trace_id,
                    "parent_id": None,
                    "name": "Agent run - Agent",
                    "start_time": span["start_time"],
                    "end_time": None,  # running
                    "status": 0,  # unset/running
                    "span_type": "agentRun",
                    "attributes": {"type": "agentRun", "agentName": "Agent"},
                }
            )
            return

        # ON_END processing
        if event_type == "on_end":
            # Check if we have active execution
            if trace_id not in self.executions:
                print("  (no active execution, pass-through)")
                return

            execution = self.executions[trace_id]

            # LangGraph root ending - emit final state
            if name == "LangGraph" and span_id == execution.langgraph_span_id:
                execution.end_time = span["end_time"]
                execution.attributes = span.get("attributes", {})
                self._finalize(execution)
                del self.executions[trace_id]
                return

            # Node span - filter out (buffer but don't emit)
            if self._is_node_span(span):
                print("  (filtered node span)")
                return

            # LLM span - emit LLM call + Model run immediately
            if self._is_llm_span(span):
                self._emit_llm_call(span, execution)
                return

            print("  (pass-through)")

    def _emit_llm_call(self, llm_span: Dict, execution: AgentExecution) -> None:
        """Emit LLM call + Model run spans."""
        execution.llm_count += 1
        llm_call_id = self._gen_id()
        attrs = llm_span.get("attributes", {})

        # Parse invocation params
        inv_params = attrs.get("llm.invocation_parameters", "{}")
        if isinstance(inv_params, str):
            try:
                inv_params = json.loads(inv_params)
            except:
                inv_params = {}

        # 1. LLM call wrapper
        self._emit(
            {
                "id": llm_call_id,
                "trace_id": execution.trace_id,
                "parent_id": execution.synthetic_span_id,
                "name": "LLM call",
                "start_time": llm_span["start_time"],
                "end_time": llm_span["end_time"],
                "status": 1,
                "span_type": "completion",
                "attributes": {"type": "completion"},
            }
        )

        # 2. Model run (child of LLM call)
        self._emit(
            {
                "id": self._gen_id(),
                "trace_id": execution.trace_id,
                "parent_id": llm_call_id,
                "name": "Model run",
                "start_time": llm_span["start_time"],
                "end_time": llm_span["end_time"],
                "status": 1,
                "span_type": "completion",
                "attributes": {
                    "type": "completion",
                    "model": attrs.get("llm.model_name", ""),
                    "usage": {
                        "promptTokens": attrs.get("llm.token_count.prompt"),
                        "completionTokens": attrs.get("llm.token_count.completion"),
                        "totalTokens": attrs.get("llm.token_count.total"),
                    },
                    "settings": inv_params,
                },
            }
        )

    def _finalize(self, execution: AgentExecution) -> None:
        """Emit final spans when LangGraph ends."""
        attrs = execution.attributes

        # Extract output
        output_value = attrs.get("output.value", "{}")
        if isinstance(output_value, str):
            try:
                output_data = json.loads(output_value)
            except:
                output_data = {}
        else:
            output_data = output_value

        # Extract prompts
        system_prompt = ""
        user_prompt = ""
        for msg in output_data.get("messages", []):
            if isinstance(msg, dict):
                if msg.get("type") == "system":
                    system_prompt = msg.get("content", "")
                elif msg.get("type") == "human":
                    user_prompt = msg.get("content", "")

        output_content = output_data.get("content", "")

        # 1. Update Agent run to COMPLETED state
        self._emit(
            {
                "id": execution.synthetic_span_id,
                "trace_id": execution.trace_id,
                "parent_id": None,
                "name": "Agent run - Agent",
                "start_time": execution.start_time,
                "end_time": execution.end_time,
                "status": 1,  # OK
                "span_type": "agentRun",
                "attributes": {
                    "type": "agentRun",
                    "agentName": "Agent",
                    "systemPrompt": system_prompt,
                    "userPrompt": user_prompt,
                    "output": {"content": output_content},
                },
            }
        )

        # 2. Agent output span
        self._emit(
            {
                "id": self._gen_id(),
                "trace_id": execution.trace_id,
                "parent_id": execution.synthetic_span_id,
                "name": "Agent output",
                "start_time": execution.end_time,
                "end_time": execution.end_time,
                "status": 1,
                "span_type": "agentOutput",
                "attributes": {
                    "type": "agentOutput",
                    "output": {"content": output_content},
                },
            }
        )


def main():
    print("=" * 60)
    print("POC: Streaming LangGraph → NotLangGraph Transform")
    print("=" * 60)

    transformer = StreamingTransformer()

    print("\n--- STREAMING INPUT EVENTS ---")
    for event in STREAMING_INPUT:
        transformer.process_event(event)

    print("\n" + "=" * 60)
    print(f"OUTPUT: {len(transformer.output_spans)} transformed spans")
    print("=" * 60)

    # Print tree structure
    spans = transformer.output_spans
    children: Dict[Optional[str], List[Dict]] = {None: []}
    for span in spans:
        pid = span.get("parent_id")
        if pid not in children:
            children[pid] = []
        children[pid].append(span)

    def print_tree(parent_id: Optional[str], indent: int = 0):
        for span in children.get(parent_id, []):
            prefix = "  " * indent + ("├── " if indent > 0 else "")
            status = "RUNNING" if span["status"] == 0 else "OK"
            print(f"{prefix}{span['name']} [{status}]")
            print_tree(span["id"], indent + 1)

    print("\nSpan Tree:")
    print_tree(None)

    # Save output
    with open("prototype/streaming_output.json", "w") as f:
        json.dump(transformer.output_spans, f, indent=2)
    print("\nSaved: prototype/streaming_output.json")


if __name__ == "__main__":
    main()
