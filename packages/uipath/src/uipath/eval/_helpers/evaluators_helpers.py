import ast
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan

from ..models import (
    ToolCall,
    ToolOutput,
)

TOOL_NAME_ATTR = "tool.name"

# Mirrors uipath_langchain.agent.tools.utils.sanitize_tool_name; pinned by TestSanitizedNameMatch.
_TOOL_NAME_DISALLOWED = re.compile(r"[^a-zA-Z0-9_-]")


def _sanitize_tool_name(name: str | None) -> str:
    """Sanitise a tool name the same way the LangChain runtime does."""
    if not name:
        return ""
    return _TOOL_NAME_DISALLOWED.sub("", "_".join(name.split()))[:64]


COMPARATOR_MAPPINGS = {
    ">": "gt",
    "<": "lt",
    ">=": "ge",
    "<=": "le",
    "=": "eq",
    "==": "eq",
    "!=": "ne",
}


def _unsynthesized_tool_attrs(span: ReadableSpan) -> Mapping[str, Any] | None:
    """Return span.attributes if this is a real tool invocation, else None."""
    attrs = span.attributes
    if (
        not attrs
        or attrs.get("tool.synthesized", False)
        or not attrs.get(TOOL_NAME_ATTR)
    ):
        return None
    return attrs


def _match_key(actual_name: str, actual_id: str | None, expected_key: str) -> bool:
    """Strict per-call kind: id-only when actual has one, sanitised-name otherwise — never cross-kind."""
    if actual_id is not None:
        return expected_key == actual_id
    return _sanitize_tool_name(expected_key) == _sanitize_tool_name(actual_name)


def _calls_match(actual, expected) -> bool:
    """Strict per-call kind: id-only when actual has one, sanitised-name otherwise — never cross-kind."""
    if actual.id is not None:
        # Picker stores the id under `expected.name` when an id was chosen — honour either field.
        expected_key = expected.id if expected.id is not None else expected.name
        return actual.id == expected_key
    return _sanitize_tool_name(actual.name) == _sanitize_tool_name(expected.name)


def _parse_tool_args(input_value: Any) -> dict[str, Any]:
    """Coerce a span's `input.value` into a dict of tool args.

    Tries JSON first (handles `true`/`false`/`null` and double-quoted keys),
    falls back to `ast.literal_eval` for Python literal syntax (single-quoted
    dict repr). Returns `{}` for non-dict parsed values or any parse failure.
    """
    if isinstance(input_value, dict):
        return input_value
    if not isinstance(input_value, str):
        return {}
    try:
        try:
            parsed = json.loads(input_value)
        except ValueError:  # JSONDecodeError is a ValueError
            parsed = ast.literal_eval(input_value)
    except (SyntaxError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _tool_id_from(attrs: Mapping[str, Any]) -> str | None:
    """Return the span's `tool.id` as a string when present, else None.

    Uses `is not None` (not truthiness) so an id of 0 or '' isn't dropped.
    """
    tool_id = attrs.get("tool.id")
    return str(tool_id) if tool_id is not None else None


def _build_tool_call(span: ReadableSpan, include_args: bool) -> ToolCall | None:
    """Build a ToolCall from a span, or None for synthesized / non-tool spans."""
    attrs = _unsynthesized_tool_attrs(span)
    if attrs is None:
        return None
    tool_name = str(attrs[TOOL_NAME_ATTR])
    tool_id = _tool_id_from(attrs)
    args = _parse_tool_args(attrs.get("input.value", {})) if include_args else {}
    return ToolCall(name=tool_name, args=args, id=tool_id)


def count_tool_calls_by_name_and_id(tool_calls: Sequence[ToolCall]) -> dict[str, int]:
    """Bucket each call under its id when present, else its name — strict per-call kind, no cross-kind matching."""
    counts: dict[str, int] = {}
    for c in tool_calls:
        key = c.id if c.id is not None else c.name
        counts[key] = counts.get(key, 0) + 1
    return counts


def extract_tool_calls_names(spans: Sequence[ReadableSpan]) -> list[str]:
    """Extract the tool call names from execution spans IN ORDER.

    Args:
        spans: List of ReadableSpan objects from agent execution.

    Returns:
        List of tool names in the order they were called.
    """
    tool_calls_names = []

    for span in spans:
        if (attrs := _unsynthesized_tool_attrs(span)) is not None:
            tool_calls_names.append(str(attrs[TOOL_NAME_ATTR]))

    return tool_calls_names


def extract_tool_calls(
    spans: Sequence[ReadableSpan],
    include_args: bool = True,
) -> list[ToolCall]:
    """Extract the tool calls from execution spans.

    Args:
        spans: List of ReadableSpan objects from agent execution.
        include_args: When False, skip parsing `input.value` and return
            ToolCall objects with `args={}`. Use for evaluators that only
            need name/id (count, order) — avoids a parse per span on large
            traces.

    Returns:
        List of tool calls with their arguments.
    """
    return [c for s in spans if (c := _build_tool_call(s, include_args)) is not None]


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
        if (attrs := _unsynthesized_tool_attrs(span)) is not None:
            tool_name = str(attrs[TOOL_NAME_ATTR])
            tool_id = _tool_id_from(attrs)
            output = attrs.get("output.value", "")
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
                    name=tool_name,
                    output=str(final_output) if final_output else "",
                    id=tool_id,
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
        "actual": str(list(actual_tool_calls_names)),
        "expected": str(list(expected_tool_calls_names)),
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


def _strict_order_score(
    actual: Sequence[ToolCall],
    expected: Sequence[str],
    justification: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    """Strict-mode evaluation — only an exact positional match scores 1.0."""
    if len(actual) != len(expected):
        return 0.0, justification
    for i, key in enumerate(expected):
        if not _match_key(actual[i].name, actual[i].id, key):
            return 0.0, justification
    justification["lcs"] = list(expected)
    return 1.0, justification


def _build_lcs_dp(
    actual: Sequence[ToolCall], expected: Sequence[str]
) -> list[list[int]]:
    """Fill the LCS dynamic-programming table for id-aware matching."""
    m, n = len(actual), len(expected)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if _match_key(actual[i - 1].name, actual[i - 1].id, expected[j - 1]):
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp


def _reconstruct_lcs(
    actual: Sequence[ToolCall],
    expected: Sequence[str],
    dp: list[list[int]],
) -> list[str]:
    """Walk the DP table backwards to recover the LCS as a list of expected keys."""
    lcs: list[str] = []
    i, j = len(actual), len(expected)
    while i > 0 and j > 0:
        if _match_key(actual[i - 1].name, actual[i - 1].id, expected[j - 1]):
            lcs.append(expected[j - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] > dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    lcs.reverse()
    return lcs


def tool_calls_order_score_with_ids(
    actual_tool_calls: Sequence[ToolCall],
    expected_tool_calls_keys: Sequence[str],
    strict: bool = False,
) -> tuple[float, dict[str, Any]]:
    """LCS-based ordering score with id-aware matching.

    Identical scoring algorithm to `tool_calls_order_score`, but each expected
    key string is allowed to match either the actual call's `id` or its
    `name`. Use this when eval-set criteria may be authored against the
    stable tool id so renames of `name` don't silently break ordering checks.

    Args:
        actual_tool_calls: ToolCall objects in the actual order. Each may carry
            an `id` from the runtime's `tool.id` span attribute.
        expected_tool_calls_keys: List of names OR ids in the expected order.
        strict: When True, only perfect matches score above 0.

    Returns:
        Same shape as `tool_calls_order_score`. The "actual" justification
        renders the resolved match-key sequence (id when available, else name)
        so the LCS reconstruction reads clearly.
    """
    actual_keys: list[str] = [
        (c.id if c.id is not None else c.name) for c in actual_tool_calls
    ]
    justification: dict[str, Any] = {
        "actual": str(list(actual_keys)),
        "expected": str(list(expected_tool_calls_keys)),
        "lcs": [],
    }

    if not expected_tool_calls_keys and not actual_tool_calls:
        return 1.0, justification
    if not expected_tool_calls_keys or not actual_tool_calls:
        return 0.0, justification

    if strict:
        return _strict_order_score(
            actual_tool_calls, expected_tool_calls_keys, justification
        )

    dp = _build_lcs_dp(actual_tool_calls, expected_tool_calls_keys)
    lcs = _reconstruct_lcs(actual_tool_calls, expected_tool_calls_keys, dp)
    justification["lcs"] = lcs
    return len(lcs) / len(expected_tool_calls_keys), justification


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
            "expected": str(dict(expected_tool_calls_count)),
            "actual": str(dict(actual_tool_calls_count)),
            justification_key: {
                "_result": "Both expected and actual tool calls are empty"
            },
        }
    elif not expected_tool_calls_count or not actual_tool_calls_count:
        return 0.0, {
            "expected": str(dict(expected_tool_calls_count)),
            "actual": str(dict(actual_tool_calls_count)),
            justification_key: {
                "_result": "Either expected or actual tool calls are empty"
            },
        }

    score = 0.0
    justifications: dict[str, Any] = {
        "expected": str(dict(expected_tool_calls_count)),
        "actual": str(dict(actual_tool_calls_count)),
        justification_key: {},
    }
    for tool_name, (
        expected_comparator,
        expected_count,
    ) in expected_tool_calls_count.items():
        # Raw key first (id-keyed / exact-match), then sanitised (legacy display-name). `is None` not `or`: count of 0 is a hit.
        actual_count = actual_tool_calls_count.get(tool_name)
        if actual_count is None:
            actual_count = actual_tool_calls_count.get(
                _sanitize_tool_name(tool_name), 0
            )
        comparator = f"__{COMPARATOR_MAPPINGS[expected_comparator]}__"
        to_add = float(getattr(actual_count, comparator)(expected_count))

        justifications[justification_key][tool_name] = (
            f"Actual: {actual_count}, Expected: {expected_count}, Score: {to_add}"
        )
        if strict and to_add == 0.0:
            # When strict is True, if the actual count does not match the expected count, return 0
            # The justification should only include the breaching tool name
            return 0.0, {
                "expected": str(dict(expected_tool_calls_count)),
                "actual": str(dict(actual_tool_calls_count)),
                justification_key: {
                    tool_name: justifications[justification_key][tool_name]
                },
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
            "expected": str(expected_tool_calls),
            "actual": str(actual_tool_calls),
            justification_key: {
                "_result": "Both expected and actual tool calls are empty"
            },
        }
    elif not expected_tool_calls or not actual_tool_calls:
        return 0.0, {
            "expected": str(expected_tool_calls),
            "actual": str(actual_tool_calls),
            justification_key: {
                "_result": "Either expected or actual tool calls are empty"
            },
        }

    cnt = 0
    visited: set[int] = set()
    justifications: dict[str, Any] = {
        "expected": str(expected_tool_calls),
        "actual": str(actual_tool_calls),
        justification_key: {},
    }
    tool_counters: dict[str, int] = {}

    for expected_tool_call in expected_tool_calls:
        for idx, call in enumerate(actual_tool_calls):
            if _calls_match(call, expected_tool_call) and idx not in visited:
                # Get or initialize counter for this tool name
                tool_counters[call.name] = tool_counters.get(call.name, 0)
                tool_key = f"{call.name}_{tool_counters[call.name]}"
                tool_counters[call.name] += 1

                # Check arguments based on mode
                if subset:
                    # Subset mode: safely check if all expected args exist and match
                    # Capture 'call' as a default argument to bind the loop variable
                    args_check = (  # noqa: E731
                        lambda k, v, call=call: k in call.args and call.args[k] == v
                    )
                else:
                    # Exact mode: direct access (may raise KeyError)
                    # Capture 'call' as a default argument to bind the loop variable
                    args_check = lambda k, v, call=call: call.args[k] == v  # noqa: E731

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
            "expected": str(expected_tool_calls_outputs),
            "actual": str(actual_tool_calls_outputs),
            justification_key: {
                "_result": "Both expected and actual tool calls outputs are empty"
            },
        }
    elif not expected_tool_calls_outputs or not actual_tool_calls_outputs:
        return 0.0, {
            "expected": str(expected_tool_calls_outputs),
            "actual": str(actual_tool_calls_outputs),
            justification_key: {
                "_result": "Either expected or actual tool calls outputs are empty"
            },
        }

    cnt = 0.0
    justifications: dict[str, Any] = {
        "expected": str(expected_tool_calls_outputs),
        "actual": str(actual_tool_calls_outputs),
        justification_key: {},
    }
    visited: set[int] = set()
    tool_counters: dict[str, int] = {}

    for expected_tool_call_output in expected_tool_calls_outputs:
        matched = False

        # Look through ALL actual tool calls to find a match
        for idx, actual_tool_call_output in enumerate(actual_tool_calls_outputs):
            if idx in visited:
                continue
            if _calls_match(actual_tool_call_output, expected_tool_call_output):
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
                        "expected": str(expected_tool_calls_outputs),
                        "actual": str(actual_tool_calls_outputs),
                        justification_key: {
                            tool_key: justifications[justification_key][tool_key]
                        },
                    }
                # In non-strict mode with mismatch, continue looking for perfect match
                # DON'T add to visited, DON'T break

        # If no match found and we're in strict mode, return 0
        if not matched and strict:
            return 0.0, {
                "expected": str(expected_tool_calls_outputs),
                "actual": str(actual_tool_calls_outputs),
                justification_key: {
                    "_result": f"No matching actual tool call found for expected {expected_tool_call_output.name}"
                },
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
        if span.attributes and (tool_name := span.attributes.get(TOOL_NAME_ATTR)):
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
