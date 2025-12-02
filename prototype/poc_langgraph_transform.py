#!/usr/bin/env python3
"""POC: Transform LangGraph spans to NotLangGraph (UiPath-native) schema.

This script demonstrates the transformation from verbose LangGraph OTLP spans
into the simplified UiPath-native schema used by NotLangGraph agents.

Input: langgraph_real.json (8 spans with LangGraph/OpenInference schema)
Output: transformed_output.json (12 spans with UiPath-native schema)
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# LangGraph node names to filter out
LANGGRAPH_NODE_NAMES: Set[str] = {"init", "agent", "action", "route_agent", "terminate"}


@dataclass
class TransformContext:
    """Tracks state during transformation."""

    trace_id: str
    synthetic_agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    synthetic_spans: List[Dict[str, Any]] = field(default_factory=list)


def load_json(filepath: str) -> List[Dict[str, Any]]:
    """Load JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def save_json(filepath: str, data: List[Dict[str, Any]]) -> None:
    """Save JSON file."""
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def parse_attributes(attrs_str: str) -> Dict[str, Any]:
    """Parse attributes JSON string."""
    if isinstance(attrs_str, dict):
        return attrs_str
    try:
        return json.loads(attrs_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def generate_uipath_id() -> str:
    """Generate UiPath-style span ID (00000000-0000-0000-XXXX-XXXXXXXXXXXX)."""
    uid = uuid.uuid4()
    # Format: first 8 bytes are zeros, last 8 bytes from uuid
    hex_str = uid.hex
    return f"00000000-0000-0000-{hex_str[16:20]}-{hex_str[20:32]}"


def is_langgraph_root(span: Dict[str, Any]) -> bool:
    """Check if span is LangGraph root."""
    return span.get("Name") == "LangGraph"


def is_node_span(span: Dict[str, Any]) -> bool:
    """Check if span is a LangGraph node to filter out."""
    name = span.get("Name", "")
    if name in LANGGRAPH_NODE_NAMES:
        return True
    if name.startswith("action:"):
        return True

    attrs = parse_attributes(span.get("Attributes", "{}"))
    metadata = attrs.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}
    return "langgraph_node" in metadata if isinstance(metadata, dict) else False


def is_llm_span(span: Dict[str, Any]) -> bool:
    """Check if span is an LLM span (UiPathChat)."""
    attrs = parse_attributes(span.get("Attributes", "{}"))
    return attrs.get("openinference.span.kind") == "LLM"


def extract_prompts_from_langgraph(langgraph_span: Dict[str, Any]) -> tuple:
    """Extract system prompt, user prompt, and output from LangGraph root span."""
    attrs = parse_attributes(langgraph_span.get("Attributes", "{}"))

    system_prompt = ""
    user_prompt = ""
    output_content = ""

    # Try output.value first, then output
    output_value = attrs.get("output.value") or attrs.get("output")

    if output_value:
        if isinstance(output_value, str):
            try:
                output_data = json.loads(output_value)
            except json.JSONDecodeError:
                output_data = {"content": output_value}
        else:
            output_data = output_value

        # Extract from messages array
        messages = output_data.get("messages", [])
        for msg in messages:
            if isinstance(msg, dict):
                msg_type = msg.get("type", "")
                content = msg.get("content", "")
                if msg_type == "system" and content:
                    system_prompt = content
                elif msg_type == "human" and content:
                    user_prompt = content

        output_content = output_data.get("content", "")

    return system_prompt, user_prompt, output_content


def extract_llm_data(llm_span: Dict[str, Any]) -> Dict[str, Any]:
    """Extract LLM model run data from UiPathChat span."""
    attrs = parse_attributes(llm_span.get("Attributes", "{}"))

    # Get model name
    model = attrs.get("llm.model_name") or attrs.get("model", "")

    # Get token usage
    usage = {
        "completionTokens": attrs.get("llm.token_count.completion")
        or attrs.get("usage", {}).get("completionTokens"),
        "promptTokens": attrs.get("llm.token_count.prompt")
        or attrs.get("usage", {}).get("promptTokens"),
        "totalTokens": attrs.get("llm.token_count.total")
        or attrs.get("usage", {}).get("totalTokens"),
    }

    # Get settings from invocation parameters
    invocation_params = attrs.get("llm.invocation_parameters", "{}")
    if isinstance(invocation_params, str):
        try:
            invocation_params = json.loads(invocation_params)
        except:
            invocation_params = {}

    settings = {}
    if invocation_params.get("max_tokens") or invocation_params.get(
        "max_completion_tokens"
    ):
        settings["maxTokens"] = invocation_params.get(
            "max_tokens"
        ) or invocation_params.get("max_completion_tokens")
    if invocation_params.get("temperature") is not None:
        settings["temperature"] = invocation_params.get("temperature")

    # Get tool calls from output
    tool_calls = []
    output = attrs.get("output", [])
    if isinstance(output, list):
        for out_msg in output:
            if isinstance(out_msg, dict):
                msg = out_msg.get("message", {})
                if msg.get("tool_calls"):
                    tool_calls = msg["tool_calls"]

    return {
        "model": model,
        "usage": usage,
        "settings": settings,
        "toolCalls": tool_calls,
    }


def create_agent_run_span(
    langgraph_span: Dict[str, Any],
    ctx: TransformContext,
) -> Dict[str, Any]:
    """Create 'Agent run - Agent' span from LangGraph root."""
    system_prompt, user_prompt, output_content = extract_prompts_from_langgraph(
        langgraph_span
    )

    agent_run_id = generate_uipath_id()
    ctx.synthetic_agent_id = agent_run_id

    return {
        "Id": agent_run_id,
        "TraceId": langgraph_span.get("TraceId"),
        "ParentId": None,
        "Name": "Agent run - Agent",
        "StartTime": langgraph_span.get("StartTime"),
        "EndTime": langgraph_span.get("EndTime"),
        "Attributes": json.dumps(
            {
                "type": "agentRun",
                "agentId": str(uuid.uuid4()),
                "agentName": "Agent",
                "systemPrompt": system_prompt,
                "userPrompt": user_prompt,
                "inputSchema": {"type": "object", "properties": {}},
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Output content"}
                    },
                },
                "input": {},
                "output": {"content": output_content},
                "source": "playground",
                "isConversational": None,
                "error": None,
            }
        ),
        "Status": langgraph_span.get("Status", 1),
        "OrganizationId": langgraph_span.get("OrganizationId"),
        "TenantId": langgraph_span.get("TenantId"),
        "ExpiryTimeUtc": None,
        "FolderKey": langgraph_span.get("FolderKey"),
        "Source": 1,
        "SpanType": "agentRun",
        "ProcessKey": langgraph_span.get("ProcessKey"),
        "JobKey": langgraph_span.get("JobKey"),
        "VerbosityLevel": 2,
        "UpdatedAt": datetime.utcnow().isoformat() + "Z",
        "Attachments": None,
    }


def create_guardrail_spans(
    parent_id: str,
    trace_id: str,
    base_span: Dict[str, Any],
    guardrail_type: str,  # "agent_pre", "agent_post", "llm_pre", "llm_post"
    start_time: str,
    end_time: str,
) -> List[Dict[str, Any]]:
    """Create guardrail check span + governance child span."""
    spans = []

    # Guardrail span config
    config = {
        "agent_pre": (
            "Agent input guardrail check",
            "agentPreGuardrails",
            "Pre-execution governance",
            "preGovernance",
        ),
        "agent_post": (
            "Agent output guardrail check",
            "agentPostGuardrails",
            "Post-execution governance",
            "postGovernance",
        ),
        "llm_pre": (
            "LLM input guardrail check",
            "llmPreGuardrails",
            "Pre-execution governance",
            "preGovernance",
        ),
        "llm_post": (
            "LLM output guardrail check",
            "llmPostGuardrails",
            "Post-execution governance",
            "postGovernance",
        ),
    }

    name, span_type, gov_name, gov_type = config[guardrail_type]

    guardrail_id = generate_uipath_id()
    governance_id = generate_uipath_id()

    # Guardrail span
    spans.append(
        {
            "Id": guardrail_id,
            "TraceId": trace_id,
            "ParentId": parent_id,
            "Name": name,
            "StartTime": start_time,
            "EndTime": end_time,
            "Attributes": json.dumps(
                {
                    "type": span_type,
                    "error": None,
                }
            ),
            "Status": 1,
            "OrganizationId": base_span.get("OrganizationId"),
            "TenantId": base_span.get("TenantId"),
            "ExpiryTimeUtc": None,
            "FolderKey": base_span.get("FolderKey"),
            "Source": 1,
            "SpanType": span_type,
            "ProcessKey": base_span.get("ProcessKey"),
            "JobKey": base_span.get("JobKey"),
            "VerbosityLevel": 2,
            "UpdatedAt": datetime.utcnow().isoformat() + "Z",
            "Attachments": None,
        }
    )

    # Governance child span
    spans.append(
        {
            "Id": governance_id,
            "TraceId": trace_id,
            "ParentId": guardrail_id,
            "Name": gov_name,
            "StartTime": start_time,
            "EndTime": end_time,
            "Attributes": json.dumps(
                {
                    "type": gov_type,
                    "policyName": "Block Audits",
                    "action": "Allow",
                    "error": None,
                }
            ),
            "Status": 1,
            "OrganizationId": base_span.get("OrganizationId"),
            "TenantId": base_span.get("TenantId"),
            "ExpiryTimeUtc": None,
            "FolderKey": base_span.get("FolderKey"),
            "Source": 1,
            "SpanType": gov_type,
            "ProcessKey": base_span.get("ProcessKey"),
            "JobKey": base_span.get("JobKey"),
            "VerbosityLevel": 2,
            "UpdatedAt": datetime.utcnow().isoformat() + "Z",
            "Attachments": None,
        }
    )

    return spans


def create_llm_call_span(
    llm_span: Dict[str, Any],
    parent_id: str,
    ctx: TransformContext,
) -> List[Dict[str, Any]]:
    """Create LLM call wrapper span with Model run child and guardrails."""
    spans = []
    trace_id = llm_span.get("TraceId")

    # LLM call wrapper span
    llm_call_id = generate_uipath_id()
    attrs = parse_attributes(llm_span.get("Attributes", "{}"))
    user_input = attrs.get("llm.input_messages.1.message.content", "")

    spans.append(
        {
            "Id": llm_call_id,
            "TraceId": trace_id,
            "ParentId": parent_id,
            "Name": "LLM call",
            "StartTime": llm_span.get("StartTime"),
            "EndTime": llm_span.get("EndTime"),
            "Attributes": json.dumps(
                {
                    "type": "llmCall",
                    "input": user_input,
                    "error": None,
                }
            ),
            "Status": llm_span.get("Status", 1),
            "OrganizationId": llm_span.get("OrganizationId"),
            "TenantId": llm_span.get("TenantId"),
            "ExpiryTimeUtc": None,
            "FolderKey": llm_span.get("FolderKey"),
            "Source": 1,
            "SpanType": "completion",
            "ProcessKey": llm_span.get("ProcessKey"),
            "JobKey": llm_span.get("JobKey"),
            "VerbosityLevel": 2,
            "UpdatedAt": datetime.utcnow().isoformat() + "Z",
            "Attachments": None,
        }
    )

    # LLM input guardrail
    spans.extend(
        create_guardrail_spans(
            llm_call_id,
            trace_id,
            llm_span,
            "llm_pre",
            llm_span.get("StartTime"),
            llm_span.get("StartTime"),
        )
    )

    # Model run span (actual LLM invocation)
    model_run_id = generate_uipath_id()
    llm_data = extract_llm_data(llm_span)

    spans.append(
        {
            "Id": model_run_id,
            "TraceId": trace_id,
            "ParentId": llm_call_id,
            "Name": "Model run",
            "StartTime": llm_span.get("StartTime"),
            "EndTime": llm_span.get("EndTime"),
            "Attributes": json.dumps(
                {
                    "type": "completion",
                    "model": llm_data["model"],
                    "settings": llm_data["settings"],
                    "toolCalls": llm_data["toolCalls"],
                    "usage": llm_data["usage"],
                    "attributes": None,
                    "error": None,
                }
            ),
            "Status": llm_span.get("Status", 1),
            "OrganizationId": llm_span.get("OrganizationId"),
            "TenantId": llm_span.get("TenantId"),
            "ExpiryTimeUtc": None,
            "FolderKey": llm_span.get("FolderKey"),
            "Source": 1,
            "SpanType": "completion",
            "ProcessKey": llm_span.get("ProcessKey"),
            "JobKey": llm_span.get("JobKey"),
            "VerbosityLevel": 2,
            "UpdatedAt": datetime.utcnow().isoformat() + "Z",
            "Attachments": None,
        }
    )

    # LLM output guardrail
    spans.extend(
        create_guardrail_spans(
            llm_call_id,
            trace_id,
            llm_span,
            "llm_post",
            llm_span.get("EndTime"),
            llm_span.get("EndTime"),
        )
    )

    return spans


def create_agent_output_span(
    langgraph_span: Dict[str, Any],
    parent_id: str,
) -> Dict[str, Any]:
    """Create Agent output span."""
    _, _, output_content = extract_prompts_from_langgraph(langgraph_span)

    return {
        "Id": generate_uipath_id(),
        "TraceId": langgraph_span.get("TraceId"),
        "ParentId": parent_id,
        "Name": "Agent output",
        "StartTime": langgraph_span.get("EndTime"),
        "EndTime": langgraph_span.get("EndTime"),
        "Attributes": json.dumps(
            {
                "type": "agentOutput",
                "output": output_content,
                "error": None,
            }
        ),
        "Status": 1,
        "OrganizationId": langgraph_span.get("OrganizationId"),
        "TenantId": langgraph_span.get("TenantId"),
        "ExpiryTimeUtc": None,
        "FolderKey": langgraph_span.get("FolderKey"),
        "Source": 1,
        "SpanType": "agentOutput",
        "ProcessKey": langgraph_span.get("ProcessKey"),
        "JobKey": langgraph_span.get("JobKey"),
        "VerbosityLevel": 2,
        "UpdatedAt": datetime.utcnow().isoformat() + "Z",
        "Attachments": None,
    }


def transform_langgraph_to_notlanggraph(
    langgraph_spans: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Transform LangGraph spans to NotLangGraph schema."""
    output_spans = []

    # Find LangGraph root and LLM spans
    langgraph_root = None
    llm_spans = []

    for span in langgraph_spans:
        if is_langgraph_root(span):
            langgraph_root = span
        elif is_llm_span(span):
            llm_spans.append(span)

    if not langgraph_root:
        print("Warning: No LangGraph root span found, returning original spans")
        return langgraph_spans

    ctx = TransformContext(trace_id=langgraph_root.get("TraceId", ""))

    # 1. Create Agent run - Agent (root)
    agent_run = create_agent_run_span(langgraph_root, ctx)
    output_spans.append(agent_run)

    # 2. Agent input guardrail check
    output_spans.extend(
        create_guardrail_spans(
            ctx.synthetic_agent_id,
            ctx.trace_id,
            langgraph_root,
            "agent_pre",
            langgraph_root.get("StartTime"),
            langgraph_root.get("StartTime"),
        )
    )

    # 3. LLM call spans (for each UiPathChat)
    for llm_span in llm_spans:
        output_spans.extend(create_llm_call_span(llm_span, ctx.synthetic_agent_id, ctx))

    # 4. Agent output guardrail check
    output_spans.extend(
        create_guardrail_spans(
            ctx.synthetic_agent_id,
            ctx.trace_id,
            langgraph_root,
            "agent_post",
            langgraph_root.get("EndTime"),
            langgraph_root.get("EndTime"),
        )
    )

    # 5. Agent output
    output_spans.append(
        create_agent_output_span(langgraph_root, ctx.synthetic_agent_id)
    )

    return output_spans


def print_span_tree(spans: List[Dict[str, Any]], title: str) -> None:
    """Print spans as a tree structure."""
    print(f"\n{'=' * 60}")
    print(f"{title} ({len(spans)} spans)")
    print("=" * 60)

    # Build parent-child map
    children: Dict[Optional[str], List[Dict]] = {None: []}
    for span in spans:
        parent_id = span.get("ParentId")
        if parent_id not in children:
            children[parent_id] = []
        children[parent_id].append(span)

    def print_node(span_id: Optional[str], indent: int = 0):
        for span in children.get(span_id, []):
            name = span.get("Name")
            span_type = span.get("SpanType")
            current_id = span.get("Id")
            prefix = "  " * indent + ("├── " if indent > 0 else "")
            print(f"{prefix}{name} (SpanType: {span_type})")
            print_node(current_id, indent + 1)

    print_node(None)


def main():
    """Run the transformation POC."""
    script_dir = Path(__file__).parent

    # Load input
    input_file = script_dir / "langgraph_real.json"
    print(f"Loading: {input_file}")
    langgraph_spans = load_json(str(input_file))

    # Print input structure
    print_span_tree(langgraph_spans, "INPUT: LangGraph spans")

    # Transform
    print("\nTransforming...")
    notlanggraph_spans = transform_langgraph_to_notlanggraph(langgraph_spans)

    # Print output structure
    print_span_tree(notlanggraph_spans, "OUTPUT: NotLangGraph spans")

    # Save output
    output_file = script_dir / "transformed_output.json"
    save_json(str(output_file), notlanggraph_spans)
    print(f"\nSaved: {output_file}")

    # Compare with expected
    expected_file = script_dir / "notlanggraph_real.json"
    if expected_file.exists():
        expected_spans = load_json(str(expected_file))
        print_span_tree(expected_spans, "EXPECTED: notlanggraph_real.json")

        print(f"\n{'=' * 60}")
        print("COMPARISON")
        print("=" * 60)
        print(f"Input spans:    {len(langgraph_spans)}")
        print(f"Output spans:   {len(notlanggraph_spans)}")
        print(f"Expected spans: {len(expected_spans)}")


if __name__ == "__main__":
    main()
