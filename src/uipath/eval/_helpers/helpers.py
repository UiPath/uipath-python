import json
import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Sequence

import click
from opentelemetry.sdk.trace import ReadableSpan

from uipath._cli._utils._console import ConsoleLogger
from uipath._utils.constants import UIPATH_CONFIG_FILE

COMPARATOR_MAPPINGS = {
    ">": "gt",
    "<": "lt",
    ">=": "ge",
    "<=": "le",
    "=": "eq",
    "!=": "ne",
}


def auto_discover_entrypoint() -> str:
    """Auto-discover entrypoint from config file.

    Returns:
        Path to the entrypoint

    Raises:
        ValueError: If no entrypoint found or multiple entrypoints exist
    """
    console = ConsoleLogger()

    if not os.path.isfile(UIPATH_CONFIG_FILE):
        raise ValueError(
            f"File '{UIPATH_CONFIG_FILE}' not found. Please run 'uipath init'."
        )

    with open(UIPATH_CONFIG_FILE, "r", encoding="utf-8") as f:
        uipath_config = json.loads(f.read())

    entrypoints = uipath_config.get("entryPoints", [])

    if not entrypoints:
        raise ValueError(
            f"No entrypoints found in {UIPATH_CONFIG_FILE}. Please run 'uipath init'."
        )

    if len(entrypoints) > 1:
        entrypoint_paths = [ep.get("filePath") for ep in entrypoints]
        raise ValueError(
            f"Multiple entrypoints found: {entrypoint_paths}. "
            f"Please specify which entrypoint to use."
        )

    entrypoint = entrypoints[0].get("filePath")
    console.info(
        f"Auto-discovered agent entrypoint: {click.style(entrypoint, fg='cyan')}"
    )
    return entrypoint


def extract_tool_calls_names(spans: Sequence[ReadableSpan]) -> list[str]:
    """Extract the tool call names from execution spans IN ORDER.

    Args:
        spans: List of ReadableSpan objects from agent execution.

    Returns:
        List of tool names in the order they were called.
    """
    tool_calls_names = []

    for span in spans:
        # Check for tool.name attribute first
        if span.attributes and (tool_name := span.attributes.get("tool.name")):
            tool_calls_names.append(tool_name)

    return tool_calls_names


def extract_tool_calls(spans: Sequence[ReadableSpan]) -> list[dict[str, Any]]:
    """Extract the tool calls from execution spans with their arguments.

    Args:
        spans: List of ReadableSpan objects from agent execution.

    Returns:
        Dict of tool calls with their arguments.
    """
    tool_calls = []

    for span in spans:
        if span.attributes and (tool_name := span.attributes.get("tool.name")):
            try:
                input_value = span.attributes.get("input.value", "{}")
                # Ensure input_value is a string before parsing
                if isinstance(input_value, str):
                    arguments = json.loads(input_value.replace("'", '"'))
                else:
                    arguments = {}
                tool_calls.append({"name": tool_name, "args": arguments})
            except json.JSONDecodeError:
                # Handle case where input.value is not valid JSON
                tool_calls.append({"name": tool_name, "args": {}})

    return tool_calls


def extract_tool_calls_outputs(spans: Sequence[ReadableSpan]) -> list[dict[str, Any]]:
    """Extract the outputs of the tool calls from execution spans."""
    tool_calls_outputs = []
    for span in spans:
        if span.attributes and (tool_name := span.attributes.get("tool.name")):
            tool_calls_outputs.append(
                {"name": tool_name, "output": span.attributes.get("output.value", {})}
            )
    return tool_calls_outputs


def tool_calls_order_score(
    actual_tool_calls_names: Sequence[str],
    expected_tool_calls_names: Sequence[str],
    strict: bool = False,
) -> tuple[float, str]:
    """The function calculates a score based on LCS applied to the order of the tool calls.

    It calculates the longest common subsequence between the actual tool calls
    and the expected tool calls and returns the ratio of the LCS length to the number of
    expected calls.

    Args:
        actual_tool_calls_names: List of tool names in the actual order
        expected_tool_calls_names: List of tool names in the expected order
        strict: If True, the function will return 0 if the actual calls do not match the expected calls

    Returns:
        tuple[float, str]: Ratio of the LCS length to the number of expected, and the LCS string
    """
    justification_template = f"Expected tool calls: {expected_tool_calls_names}\nActual tool calls: {actual_tool_calls_names}"
    if not strict:
        justification_template += "\nLongest common subsequence: {lcs}"
    if expected_tool_calls_names == actual_tool_calls_names:
        return 1.0, justification_template.format(lcs=actual_tool_calls_names)
    elif (
        not expected_tool_calls_names
        or not actual_tool_calls_names
        or strict
        and actual_tool_calls_names != expected_tool_calls_names
    ):
        return 0.0, justification_template.format(lcs="")

    # Calculate LCS with full DP table for efficient reconstruction
    m, n = len(actual_tool_calls_names), len(expected_tool_calls_names)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # Build DP table - O(m*n)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if actual_tool_calls_names[i - 1] == expected_tool_calls_names[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    # Reconstruct LCS - O(m+n)
    lcs = []
    i, j = m, n
    while i > 0 and j > 0:
        if actual_tool_calls_names[i - 1] == expected_tool_calls_names[j - 1]:
            lcs.append(actual_tool_calls_names[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] > dp[i][j - 1]:
            i -= 1
        else:
            j -= 1

    lcs.reverse()  # Reverse to get correct order
    lcs_length = len(lcs)
    return lcs_length / n, justification_template.format(lcs=" ".join(lcs))


def tool_calls_count_score(
    actual_tool_calls_count: Mapping[str, int],
    expected_tool_calls_count: Mapping[str, tuple[str, int]],
    strict: bool = False,
) -> tuple[float, str]:
    """Check if the expected tool calls are correctly called, where expected args must be a subset of actual args.

    It does not check the order of the tool calls!
    """
    if not expected_tool_calls_count and not actual_tool_calls_count:
        return 1.0, "Both expected and actual tool calls are empty"
    elif not expected_tool_calls_count or not actual_tool_calls_count:
        return 0.0, "Either expected or actual tool calls are empty"

    score = 0.0
    justifications = []
    for tool_name, (
        expected_comparator,
        expected_count,
    ) in expected_tool_calls_count.items():
        actual_count = actual_tool_calls_count.get(tool_name, 0.0)
        comparator = f"__{COMPARATOR_MAPPINGS[expected_comparator]}__"
        to_add = float(getattr(actual_count, comparator)(expected_count))
        justifications.append(
            f"{tool_name}: Actual count: {actual_count}, Expected count: {expected_count}, Score: {to_add}"
        )
        if strict and to_add == 0.0:
            return 0.0, justifications[-1]
        score += to_add
    return score / len(expected_tool_calls_count), "\n".join(justifications)


def tool_args_score(
    actual_tool_calls: list[dict[str, Any]],
    expected_tool_calls: list[dict[str, Any]],
    strict: bool = False,
    subset: bool = False,
) -> float:
    """Check if the expected tool calls are correctly called, where expected args must be a subset of actual args.

    This function does not check the order of the tool calls!

    Arguments:
        actual_tool_calls (list[Dict[str, Any]]): List of actual tool calls in the format of {"name": str, "args": Dict[str, Any]}
        expected_tool_calls (list[Dict[str, Any]]): List of expected tool calls in the format of {"name": str, "args": Dict[str, Any]}
        strict (bool): If True, the function will return 0 if not all expected tool calls are matched
        subset (bool): If True, the function will check if the expected args are a subset of the actual args

    Returns:
        float: Score based on the number of matches
    """
    cnt = 0
    visited: set[int] = set()

    for expected_tool_call in expected_tool_calls:
        for idx, call in enumerate(actual_tool_calls):
            if (
                call.get("name") == expected_tool_call.get("name")
                and idx not in visited
            ):
                # Check arguments based on mode
                if subset:
                    # Subset mode: safely check if all expected args exist and match
                    args_check = (  # noqa: E731
                        lambda k, v: k in call.get("args", {})  # noqa: B023
                        and call.get("args", {})[k] == v  # noqa: B023
                    )
                    validator_check = lambda k, validator: k not in call.get(  # noqa: E731, B023
                        "args", {}
                    ) or validator(call.get("args", {})[k])  # noqa: B023
                else:
                    # Exact mode: direct access (may raise KeyError)
                    args_check = lambda k, v: call.get("args", {})[k] == v  # noqa: E731, B023
                    validator_check = lambda k, validator: validator(  # noqa: E731
                        call.get("args", {})[k]  # noqa: B023
                    )

                try:
                    args_match = all(
                        args_check(k, v)
                        for k, v in expected_tool_call.get("args", {}).items()
                    )
                    validators_match = True
                    if expected_tool_call.get("args_validators", {}):
                        validators_match = all(
                            validator_check(k, validator)
                            for k, validator in expected_tool_call.get(
                                "args_validators", {}
                            ).items()
                        )
                except KeyError:
                    # Only possible in exact mode when key is missing
                    args_match = False
                    validators_match = False
                if args_match and validators_match:
                    cnt += 1
                    visited.add(idx)
                    break

    return (
        cnt / len(expected_tool_calls)
        if not strict
        else float(cnt == len(expected_tool_calls))
    )


def tool_output_score(
    actual_tool_calls_outputs: list[dict[str, Any]],
    expected_tool_calls_outputs: list[dict[str, Any]],
    strict: bool = False,
) -> float:
    """Check if the expected tool calls are correctly called, where expected args must be a subset of actual args.

    This function does not check the order of the tool calls!
    """
    if not expected_tool_calls_outputs and not actual_tool_calls_outputs:
        return 1.0
    elif (
        not expected_tool_calls_outputs
        or not actual_tool_calls_outputs
        or strict
        and actual_tool_calls_outputs != expected_tool_calls_outputs
    ):
        return 0.0

    cnt = 0.0
    for expected_tool_call_output in expected_tool_calls_outputs:
        for actual_tool_call_output in actual_tool_calls_outputs:
            if actual_tool_call_output.get("name") == expected_tool_call_output.get(
                "name"
            ):
                if json.loads(actual_tool_call_output.get("output", "{}")).get(
                    "content"
                ) == expected_tool_call_output.get("output"):
                    cnt += 1.0
                elif strict:
                    return 0.0
    return (
        cnt / len(expected_tool_calls_outputs)
        if not strict
        else float(cnt == len(expected_tool_calls_outputs))
    )


def trace_to_str(agent_trace: Sequence[ReadableSpan]) -> str:
    """Convert OTEL spans to a platform-style agent run history string.

    Creates a similar structure to LangChain message processing but using OTEL spans.
    Only processes tool spans (spans with 'tool.name' attribute).

    Args:
        agent_trace: List of ReadableSpan objects from the agent execution

    Returns:
        String representation of the agent run history in platform format
    """
    platform_history = []
    seen_tool_calls = set()

    for span in agent_trace:
        if span.attributes and (tool_name := span.attributes.get("tool.name")):
            # Get span timing information
            start_time = span.start_time
            end_time = span.end_time

            # Convert nanoseconds to datetime if needed
            if isinstance(start_time, int):
                start_timestamp = datetime.fromtimestamp(start_time / 1e9)
            else:
                start_timestamp = start_time

            if isinstance(end_time, int):
                end_timestamp = datetime.fromtimestamp(end_time / 1e9)
            else:
                end_timestamp = end_time

            timestamp_str = (
                start_timestamp.strftime("%Y-%m-%d %H:%M:%S") if start_timestamp else ""
            )

            # Get tool call information
            tool_args = span.attributes.get("input.value", {})
            tool_result = span.attributes.get("output.value", "{}")
            # Attempt to extract only the content of the tool result if it is a string
            if isinstance(tool_result, str):
                try:
                    tool_result = json.loads(tool_result.replace("'", '"'))["content"]
                except (json.JSONDecodeError, KeyError):
                    tool_result = tool_result

            span_id = (
                span.context.span_id
                if span.context
                else str(hash(f"{tool_name}_{timestamp_str}"))
            )

            # De-duplicate tool calls based on span ID
            if span_id in seen_tool_calls:
                continue
            seen_tool_calls.add(span_id)

            # Add tool selection (equivalent to AIMessage with tool_calls)
            platform_history.append(f"[{timestamp_str}] LLM Response:")
            platform_history.append("  Agent Selected 1 Tool(s):")
            platform_history.append("")
            platform_history.append(f"  Tool: {tool_name}")
            platform_history.append(f"  Arguments: {str(tool_args)}")
            platform_history.append("")

            # Add tool response (equivalent to ToolMessage)
            end_timestamp_str = (
                end_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if end_timestamp
                else timestamp_str
            )
            platform_history.append(
                f"[{end_timestamp_str}] Tool Call Response - {tool_name}:"
            )
            platform_history.append(f"{str(tool_result).strip()}")
            platform_history.append("")

    return "\n".join(platform_history)
