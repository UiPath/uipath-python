import ast
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan

from ..models import (
    ToolCall,
    ToolOutput,
)

COMPARATOR_MAPPINGS = {
    ">": "gt",
    "<": "lt",
    ">=": "ge",
    "<=": "le",
    "=": "eq",
    "==": "eq",
    "!=": "ne",
}

COMMUNITY_agents_SUFFIX = "-community-agents"


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
            tool_calls_names.append(str(tool_name))

    return tool_calls_names


def extract_tool_calls(spans: Sequence[ReadableSpan]) -> list[ToolCall]:
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
                input_value: Any = span.attributes.get("input.value", {})
                # Ensure input_value is a string before parsing
                if isinstance(input_value, str):
                    arguments = ast.literal_eval(input_value)
                elif isinstance(input_value, dict):
                    arguments = input_value
                else:
                    arguments = {}
                tool_calls.append(ToolCall(name=str(tool_name), args=arguments))
            except (json.JSONDecodeError, SyntaxError, ValueError):
                # Handle case where input.value is not valid JSON/Python syntax
                tool_calls.append(ToolCall(name=str(tool_name), args={}))

    return tool_calls


def extract_tool_calls_outputs(spans: Sequence[ReadableSpan]) -> list[ToolOutput]:
    """Extract the outputs of the tool calls from execution spans.

    Args:
        spans: List of ReadableSpan objects from agent execution.

    Returns:
        List of tool calls outputs.
    """
    # After span normalization, the output.value should always be a dict with a content field
    # We keep this list of potential output keys for extensibility purposes (e.g. frameworks without span normalization)
    potential_output_keys = ["content"]
    tool_calls_outputs = []
    for span in spans:
        if span.attributes and (tool_name := span.attributes.get("tool.name")):
            output = span.attributes.get("output.value", "")
            final_output = ""

            # Handle different output formats
            if isinstance(output, str):
                try:
                    # Try to parse as JSON and extract content field
                    parsed_output = json.loads(output)
                    if isinstance(parsed_output, dict):
                        for key in potential_output_keys:
                            if key in parsed_output:
                                final_output = parsed_output[key]
                                break
                    else:
                        # If parsed JSON is not a dict, use the original string
                        final_output = output
                except (json.JSONDecodeError, ValueError):
                    # If parsing fails, use the string as-is
                    final_output = output
            elif isinstance(output, dict):
                # If output is already a dict, extract content field
                for key in potential_output_keys:
                    if key in output:
                        final_output = output.get(key, "")
                        break
            else:
                final_output = str(output)

            tool_calls_outputs.append(
                ToolOutput(
                    name=str(tool_name),
                    output=str(final_output) if final_output else "",
                )
            )
    return tool_calls_outputs


def tool_calls_order_score(
    actual_tool_calls_names: Sequence[str],
    expected_tool_calls_names: Sequence[str],
    strict: bool = False,
) -> tuple[float, dict[str, Any]]:
    """The function calculates a score based on LCS applied to the order of the tool calls.

    It calculates the longest common subsequence between the actual tool calls
    and the expected tool calls and returns the ratio of the LCS length to the number of
    expected calls.

    Args:
        actual_tool_calls_names: List of tool names in the actual order
        expected_tool_calls_names: List of tool names in the expected order
        strict: If True, the function will return 0 if the actual calls do not match the expected calls exactly

    Returns:
        tuple[float, dict]: Ratio of the LCS length to the number of expected, and the justification dict
    """
    justification = {
        "actual_tool_calls_order": list(actual_tool_calls_names),
        "expected_tool_calls_order": list(expected_tool_calls_names),
        "lcs": [],
    }

    # Handle empty cases
    if not expected_tool_calls_names and not actual_tool_calls_names:
        return 1.0, justification
    elif not expected_tool_calls_names or not actual_tool_calls_names:
        return 0.0, justification

    # Handle exact match
    if expected_tool_calls_names == actual_tool_calls_names:
        justification["lcs"] = list(actual_tool_calls_names)
        return 1.0, justification

    # Handle strict mode - only perfect matches allowed
    if strict:
        return 0.0, justification

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
    justification["lcs"] = lcs
    return lcs_length / n, justification


def tool_calls_count_score(
    actual_tool_calls_count: Mapping[str, int],
    expected_tool_calls_count: Mapping[str, tuple[str, int]],
    strict: bool = False,
    justification_key: str = "explained_tool_calls_count",
) -> tuple[float, dict[str, Any]]:
    """Check if the expected tool call counts match the actual tool call counts.

    Args:
        actual_tool_calls_count: Mapping of tool names to their actual call counts.
        expected_tool_calls_count: Mapping of tool names to expected (comparator, count) tuples.
        strict: If True, the function will return 0 if not all expected tool calls are matched.
        justification_key: Key to use for the justification in the returned dict.

    Returns:
        tuple[float, dict]: Score based on the number of matches, and the justification dict.
    """
    if not expected_tool_calls_count and not actual_tool_calls_count:
        return 1.0, {
            justification_key: {
                "_result": "Both expected and actual tool calls are empty"
            }
        }
    elif not expected_tool_calls_count or not actual_tool_calls_count:
        return 0.0, {
            justification_key: {
                "_result": "Either expected or actual tool calls are empty"
            }
        }

    score = 0.0
    justifications: dict[str, Any] = {justification_key: {}}
    for tool_name, (
        expected_comparator,
        expected_count,
    ) in expected_tool_calls_count.items():
        actual_count = actual_tool_calls_count.get(tool_name, 0.0)
        comparator = f"__{COMPARATOR_MAPPINGS[expected_comparator]}__"
        to_add = float(getattr(actual_count, comparator)(expected_count))

        justifications[justification_key][tool_name] = (
            f"Actual: {actual_count}, Expected: {expected_count}, Score: {to_add}"
        )
        if strict and to_add == 0.0:
            # When strict is True, if the actual count does not match the expected count, return 0
            # The justification should only include the breaching tool name
            return 0.0, {
                justification_key: {
                    tool_name: justifications[justification_key][tool_name]
                }
            }
        score += to_add
    return score / len(expected_tool_calls_count), justifications


def tool_calls_args_score(
    actual_tool_calls: list[ToolCall],
    expected_tool_calls: list[ToolCall],
    strict: bool = False,
    subset: bool = False,
    justification_key: str = "explained_tool_calls_args",
) -> tuple[float, dict[str, Any]]:
    """Check if the expected tool calls are correctly called with matching arguments.

    This function does not check the order of the tool calls!

    Args:
        actual_tool_calls: List of actual tool calls with their arguments.
        expected_tool_calls: List of expected tool calls with their arguments.
        strict: If True, the function will return 0 if not all expected tool calls are matched.
        subset: If True, the function will check if the expected args are a subset of the actual args.
        justification_key: Key to use for the justification in the returned dict.

    Returns:
        tuple[float, dict]: Score based on the number of matches, and the justification dict.
    """
    if not expected_tool_calls and not actual_tool_calls:
        return 1.0, {
            justification_key: {
                "_result": "Both expected and actual tool calls are empty"
            }
        }
    elif not expected_tool_calls or not actual_tool_calls:
        return 0.0, {
            justification_key: {
                "_result": "Either expected or actual tool calls are empty"
            }
        }

    cnt = 0
    visited: set[int] = set()
    justifications: dict[str, Any] = {justification_key: {}}
    tool_counters: dict[str, int] = {}

    for expected_tool_call in expected_tool_calls:
        for idx, call in enumerate(actual_tool_calls):
            if call.name == expected_tool_call.name and idx not in visited:
                # Get or initialize counter for this tool name
                tool_counters[call.name] = tool_counters.get(call.name, 0)
                tool_key = f"{call.name}_{tool_counters[call.name]}"
                tool_counters[call.name] += 1

                # Check arguments based on mode
                # The linter highlights a few problems here due to using lambdas, but they're safe to ignore
                # Breaking this down into proper functions would unnecessarily make the code more complex
                if subset:
                    # Subset mode: safely check if all expected args exist and match
                    args_check = (  # noqa: E731
                        lambda k, v: k in call.args  # noqa: B023
                        and call.args[k] == v  # noqa: B023
                    )
                else:
                    # Exact mode: direct access (may raise KeyError)
                    args_check = lambda k, v: call.args[k] == v  # noqa: E731, B023

                try:
                    args_match = all(
                        args_check(k, v) for k, v in expected_tool_call.args.items()
                    )
                except KeyError:
                    # Only possible in exact mode when key is missing
                    args_match = False

                justifications[justification_key][tool_key] = (
                    f"Actual: {call.args}, Expected: {expected_tool_call.args}, Score: {float(args_match)}"
                )
                if args_match:
                    cnt += 1
                    visited.add(idx)
                    break
                # In case of mismatch, DON'T add to visited in non-strict mode
                # so this actual tool call can be matched against other expected calls

    return (
        cnt / len(expected_tool_calls)
        if not strict
        else float(cnt == len(expected_tool_calls))
    ), justifications


def tool_calls_output_score(
    actual_tool_calls_outputs: list[ToolOutput],
    expected_tool_calls_outputs: list[ToolOutput],
    strict: bool = False,
    justification_key: str = "explained_tool_calls_outputs",
) -> tuple[float, dict[str, Any]]:
    """Check if the expected tool calls are correctly called, where expected args must be a subset of actual args.

    Args:
        actual_tool_calls_outputs: List of actual tool calls outputs.
        expected_tool_calls_outputs: List of expected tool calls outputs.
        strict: If True, the function will return 0 if not all expected tool calls are matched.

    Returns:
        tuple[float, str]: Score based on the number of matches, and the justification.
    """
    if not expected_tool_calls_outputs and not actual_tool_calls_outputs:
        return 1.0, {
            justification_key: {
                "_result": "Both expected and actual tool calls outputs are empty"
            }
        }
    elif not expected_tool_calls_outputs or not actual_tool_calls_outputs:
        return 0.0, {
            justification_key: {
                "_result": "Either expected or actual tool calls outputs are empty"
            }
        }

    cnt = 0.0
    justifications: dict[str, Any] = {justification_key: {}}
    visited: set[int] = set()
    tool_counters: dict[str, int] = {}

    for expected_tool_call_output in expected_tool_calls_outputs:
        matched = False

        # Look through ALL actual tool calls to find a match
        for idx, actual_tool_call_output in enumerate(actual_tool_calls_outputs):
            if idx in visited:
                continue
            if actual_tool_call_output.name == expected_tool_call_output.name:
                # Get or initialize counter for this tool name
                tool_counters[actual_tool_call_output.name] = tool_counters.get(
                    actual_tool_call_output.name, 0
                )
                tool_key = f"{actual_tool_call_output.name}_{tool_counters[actual_tool_call_output.name]}"
                tool_counters[actual_tool_call_output.name] += 1

                justifications[justification_key][tool_key] = (
                    f"Actual: {actual_tool_call_output.output}, Expected: {expected_tool_call_output.output}, Score: {float(actual_tool_call_output.output == expected_tool_call_output.output)}"
                )

                if actual_tool_call_output.output == expected_tool_call_output.output:
                    # Perfect match found
                    cnt += 1.0
                    visited.add(idx)
                    matched = True
                    break
                elif strict:
                    # In strict mode, any mismatch returns 0 immediately
                    return 0.0, {
                        justification_key: {
                            tool_key: justifications[justification_key][tool_key]
                        }
                    }
                # In non-strict mode with mismatch, continue looking for perfect match
                # DON'T add to visited, DON'T break

        # If no match found and we're in strict mode, return 0
        if not matched and strict:
            return 0.0, {
                justification_key: {
                    "_result": f"No matching actual tool call found for expected {expected_tool_call_output.name}"
                }
            }

    return (
        cnt / len(expected_tool_calls_outputs)
        if not strict
        else float(cnt == len(expected_tool_calls_outputs))
    ), justifications


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
                start_timestamp = start_time  # type:ignore

            if isinstance(end_time, int):
                end_timestamp = datetime.fromtimestamp(end_time / 1e9)
            else:
                end_timestamp = end_time  # type:ignore

            timestamp_str = (
                start_timestamp.strftime("%Y-%m-%d %H:%M:%S") if start_timestamp else ""
            )

            # Get tool call information
            tool_args: Any = span.attributes.get("input.value", {})
            tool_result = str(span.attributes.get("output.value", {})).strip()

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
            platform_history.append(f"{tool_result}")
            platform_history.append("")

    return "\n".join(platform_history)
