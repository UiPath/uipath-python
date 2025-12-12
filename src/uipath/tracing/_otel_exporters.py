import json
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

import httpx
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)

from uipath._utils._ssl_context import get_httpx_client_kwargs

from ._utils import _SpanUtils

logger = logging.getLogger(__name__)


def _safe_parse_json(s: Any) -> Any:
    """Safely parse a JSON string, returning the original if not a string or on error."""
    if not isinstance(s, str):
        return s
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return s


def _get_llm_messages(attributes: Dict[str, Any], prefix: str) -> List[Dict[str, Any]]:
    """Extracts and reconstructs LLM messages from flattened attributes."""
    messages: dict[int, dict[str, Any]] = {}
    message_prefix = f"{prefix}."
    prefix_len = len(message_prefix)

    for key, value in attributes.items():
        if key.startswith(message_prefix):
            # Avoid repeated string slicing and splits
            parts = key[prefix_len:].split(".")
            if len(parts) >= 2 and parts[0].isdigit():
                index = int(parts[0])
                if index not in messages:
                    messages[index] = {}
                current: Any = messages[index]

                # Traverse parts except the last one
                parts_len = len(parts)
                for i in range(1, parts_len - 1):
                    part = parts[i]
                    key_part: str | int = part
                    if part.isdigit() and (
                        i + 2 < parts_len and parts[i + 2].isdigit()
                    ):
                        key_part = int(part)

                    if isinstance(current, dict):
                        if key_part not in current:
                            current[key_part] = {}
                        current = current[key_part]
                    elif isinstance(current, list) and isinstance(key_part, int):
                        if key_part >= len(current):
                            current.append({})
                        current = current[key_part]

                current[parts[-1]] = value

    # Convert dict to list, ordered by index, avoid sorted() if we can use range
    if not messages:
        return []

    # Convert dict to list, ordered by index
    return [messages[i] for i in sorted(messages.keys())]


class LlmOpsHttpExporter(SpanExporter):
    """An OpenTelemetry span exporter that sends spans to UiPath LLM Ops."""

    ATTRIBUTE_MAPPING: dict[str, str | tuple[str, Any]] = {
        "input.value": ("input", _safe_parse_json),
        "output.value": ("output", _safe_parse_json),
        "llm.model_name": "model",
    }

    # Mapping of span types
    SPAN_TYPE_MAPPING: dict[str, str] = {
        "LLM": "completion",
        "TOOL": "toolCall",
        # Add more mappings as needed
    }

    class Status:
        SUCCESS = 1
        ERROR = 2
        INTERRUPTED = 3

    def __init__(
        self,
        trace_id: Optional[str] = None,
        span_filter: Optional[Callable[[Dict[str, Any]], bool]] = None,
        **kwargs,
    ):
        """Initialize the exporter with the base URL and authentication token.

        Args:
            trace_id: Optional custom trace ID to use for all spans
            span_filter: Optional filter function that takes a span dict and returns True
                        if the span should be filtered out (dropped). Children of filtered
                        spans will be reparented to the filtered span's parent.
        """
        super().__init__(**kwargs)
        self.base_url = self._get_base_url()
        self.auth_token = os.environ.get("UIPATH_ACCESS_TOKEN")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
        }

        client_kwargs = get_httpx_client_kwargs()

        self.http_client = httpx.Client(**client_kwargs, headers=self.headers)
        self.trace_id = trace_id
        self.span_filter = span_filter

        # Track filtered span IDs across batches: filtered_id -> new_parent_id
        self._reparent_mapping: Dict[str, str] = {}

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export spans to UiPath LLM Ops."""
        if len(spans) == 0:
            logger.warning("No spans to export")
            return SpanExportResult.SUCCESS

        logger.debug(
            f"Exporting {len(spans)} spans to {self.base_url}/llmopstenant_/api/Traces/spans"
        )

        # Use optimized path: keep attributes as dict for processing
        # Only serialize at the very end
        span_list = [
            _SpanUtils.otel_span_to_uipath_span(
                span, custom_trace_id=self.trace_id, serialize_attributes=False
            ).to_dict(serialize_attributes=False)
            for span in spans
        ]

        # Apply filtering and reparenting if filter is configured
        filter_enabled = os.environ.get("UIPATH_FILTER_PARENT_SPAN")
        if filter_enabled:
            span_list = self._filter_and_reparent_spans(span_list)

        if len(span_list) == 0:
            logger.debug("No spans to export after filtering")
            return SpanExportResult.SUCCESS

        url = self._build_url(span_list)

        # Process spans in-place - work directly with dict
        for span_data in span_list:
            self._process_span_attributes(span_data)

        # Serialize attributes once at the very end
        for span_data in span_list:
            if isinstance(span_data.get("Attributes"), dict):
                span_data["Attributes"] = json.dumps(span_data["Attributes"])

        # Only serialize for logging if debug is enabled to avoid allocation
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Payload: %s", json.dumps(span_list))

        return self._send_with_retries(url, span_list)

    def _filter_and_reparent_spans(
        self, span_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter out spans and reparent their children.

        Rules:
        1. Root spans (uipath.is_root=True) are DROPPED, children reparented to UIPATH_PARENT_SPAN_ID
        2. Spans matching span_filter are DROPPED, children reparented to filtered span's parent

        Args:
            span_list: List of span dicts to filter

        Returns:
            Filtered list of spans with updated ParentIds
        """
        new_parent_id = os.environ.get("UIPATH_PARENT_SPAN_ID")
        if not new_parent_id:
            logger.info("[Filter] UIPATH_PARENT_SPAN_ID not set, skipping filtering")
            return span_list

        logger.info(
            f"[Filter] Starting filter with {len(span_list)} spans, "
            f"UIPATH_PARENT_SPAN_ID={new_parent_id}, "
            f"span_filter={'set' if self.span_filter else 'not set'}"
        )

        # First pass: identify spans to filter and build reparent mapping
        logger.info("[Filter] === FIRST PASS: Identifying spans to filter ===")
        for span in span_list:
            span_id = span.get("Id")
            span_name = span.get("Name")
            span_parent_id = span.get("ParentId")
            attributes = span.get("Attributes", {})

            logger.info(
                f"[Filter] Checking span: Id={span_id}, Name={span_name}, "
                f"ParentId={span_parent_id}, attributes_type={type(attributes).__name__}"
            )

            if not isinstance(attributes, dict):
                logger.info("[Filter]   -> Skipping (attributes not a dict)")
                continue

            is_root = attributes.get("uipath.is_root", False)
            original_parent_id = attributes.get("uipath.original_parent_id")

            logger.info(
                f"[Filter]   -> is_root={is_root}, original_parent_id={original_parent_id}"
            )

            # Rule 1: Root spans are dropped, children go to UIPATH_PARENT_SPAN_ID
            if is_root:
                self._reparent_mapping[span_id] = new_parent_id
                logger.info(
                    f"[Filter] Root span marked for filtering: "
                    f"Id={span_id}, Name={span.get('Name')}, "
                    f"children will be reparented to {new_parent_id}"
                )
                continue

            # Rule 2: Check custom filter function
            if not self.span_filter:
                logger.info("[Filter]   -> KEEP (no custom filter set)")
                continue

            filter_result = self.span_filter(span)
            logger.info(f"[Filter]   -> Custom filter result: {filter_result}")

            if not filter_result:
                logger.info("[Filter]   -> KEEP (custom filter returned False)")
                continue

            # Filtered span's children go to this span's parent
            # Use original_parent_id if available, otherwise use current ParentId
            parent = original_parent_id or span.get("ParentId")
            if parent:
                # Check if parent itself was filtered (transitive reparenting)
                while parent in self._reparent_mapping:
                    parent = self._reparent_mapping[parent]
                self._reparent_mapping[span_id] = parent
            else:
                self._reparent_mapping[span_id] = new_parent_id
            logger.info(
                f"[Filter]   -> WILL FILTER (custom filter matched), "
                f"children will be reparented to {self._reparent_mapping[span_id]}"
            )

        logger.info(
            f"[Filter] After first pass, reparent_mapping has {len(self._reparent_mapping)} entries: "
            f"{self._reparent_mapping}"
        )

        # Second pass: filter spans and reparent children
        logger.info("[Filter] === SECOND PASS: Filtering and reparenting ===")
        filtered_spans = []
        for span in span_list:
            span_id = span.get("Id")
            span_name = span.get("Name")
            parent_id = span.get("ParentId")

            # Skip filtered spans
            if span_id in self._reparent_mapping:
                logger.info(
                    f"[Filter] DROPPING span: Id={span_id}, Name={span_name}"
                )
                continue

            # Reparent if parent was filtered
            if parent_id and parent_id in self._reparent_mapping:
                old_parent = parent_id
                # Follow the chain for transitive reparenting
                while parent_id in self._reparent_mapping:
                    parent_id = self._reparent_mapping[parent_id]
                span["ParentId"] = parent_id
                logger.info(
                    f"[Filter] REPARENTING span: Id={span_id}, Name={span_name}, "
                    f"ParentId: {old_parent} -> {parent_id}"
                )
            else:
                logger.info(
                    f"[Filter] KEEPING span unchanged: Id={span_id}, Name={span_name}, "
                    f"ParentId={parent_id}"
                )

            filtered_spans.append(span)

        logger.info(
            f"[Filter] Complete: {len(span_list)} input -> {len(filtered_spans)} output spans, "
            f"mapping size: {len(self._reparent_mapping)}"
        )
        return filtered_spans

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush the exporter."""
        return True

    def _map_llm_call_attributes(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Maps attributes for LLM calls, handling flattened keys."""
        # Modify attributes in place to avoid copy
        result = attributes

        # Token Usage
        token_keys = {
            "llm.token_count.prompt": "promptTokens",
            "llm.token_count.completion": "completionTokens",
            "llm.token_count.total": "totalTokens",
        }
        usage = {
            new_key: attributes.get(old_key)
            for old_key, new_key in token_keys.items()
            if old_key in attributes
        }
        if usage:
            result["usage"] = usage

        # Input/Output Messages
        result["input"] = _get_llm_messages(attributes, "llm.input_messages")
        output_messages = _get_llm_messages(attributes, "llm.output_messages")
        result["output"] = output_messages

        # Invocation Parameters
        invocation_params = _safe_parse_json(
            attributes.get("llm.invocation_parameters", "{}")
        )
        if isinstance(invocation_params, dict):
            result["model"] = invocation_params.get("model", result.get("model"))
            settings: dict[str, Any] = {}
            if "max_tokens" in invocation_params:
                settings["maxTokens"] = invocation_params["max_tokens"]
            if "temperature" in invocation_params:
                settings["temperature"] = invocation_params["temperature"]
            if settings:
                result["settings"] = settings

        # Tool Calls
        tool_calls: list[dict[str, Any]] = []
        for msg in output_messages:
            # Ensure msg is a dictionary before proceeding
            if not isinstance(msg, dict):
                continue
            msg_tool_calls = msg.get("message", {}).get("tool_calls", [])

            # Ensure msg_tool_calls is a list
            if not isinstance(msg_tool_calls, list):
                continue

            for tc in msg_tool_calls:
                if not isinstance(tc, dict):
                    continue
                tool_call_data = tc.get("tool_call", {})
                if not isinstance(tool_call_data, dict):
                    continue
                tool_calls.append(
                    {
                        "id": tool_call_data.get("id"),
                        "name": tool_call_data.get("function", {}).get("name"),
                        "arguments": _safe_parse_json(
                            tool_call_data.get("function", {}).get("arguments", "{}")
                        ),
                    }
                )
        if tool_calls:
            result["toolCalls"] = tool_calls

        return result

    def _map_tool_call_attributes(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Maps attributes for tool calls."""
        # Modify attributes in place to avoid copy
        result = attributes

        result["type"] = "toolCall"
        result["callId"] = attributes.get("call_id") or attributes.get("id")
        result["toolName"] = attributes.get("tool.name")
        result["arguments"] = _safe_parse_json(
            attributes.get("input", attributes.get("input.value", "{}"))
        )
        result["toolType"] = "Integration"
        result["result"] = _safe_parse_json(
            attributes.get("output", attributes.get("output.value"))
        )
        result["error"] = None

        return result

    def _determine_status(self, error: Optional[str]) -> int:
        if error:
            if error and error.startswith("GraphInterrupt("):
                return self.Status.INTERRUPTED
            return self.Status.ERROR
        return self.Status.SUCCESS

    def _process_span_attributes(self, span_data: Dict[str, Any]) -> None:
        """Extracts, transforms, and maps attributes for a span in-place.

        Args:
            span_data: Span dict with Attributes as dict or JSON string

        Note:
            Modifies span_data in-place. When optimized path is used (dict),
            modifies dict directly. When legacy path is used (str), parse → modify → serialize.
        """
        if "Attributes" not in span_data:
            return

        attributes_val = span_data["Attributes"]
        if isinstance(attributes_val, str):
            # Legacy path: parse JSON string
            try:
                attributes: Dict[str, Any] = json.loads(attributes_val)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse attributes JSON: {e}")
                return
        elif isinstance(attributes_val, dict):
            # Optimized path: work directly with dict
            attributes = attributes_val
        else:
            return

        # Determine SpanType
        if "openinference.span.kind" in attributes:
            span_type = attributes["openinference.span.kind"]
            span_data["SpanType"] = self.SPAN_TYPE_MAPPING.get(span_type, span_type)

        # Apply basic attribute mapping
        for old_key, mapping in self.ATTRIBUTE_MAPPING.items():
            if old_key in attributes:
                if isinstance(mapping, tuple):
                    new_key, func = mapping
                    attributes[new_key] = func(attributes[old_key])
                else:
                    new_key = mapping
                    attributes[new_key] = attributes[old_key]

        # Apply detailed mapping based on SpanType
        # Modify attributes dict in place to avoid allocations
        span_type = span_data.get("SpanType")
        if span_type == "completion":
            self._map_llm_call_attributes(attributes)
        elif span_type == "toolCall":
            self._map_tool_call_attributes(attributes)

        # If attributes were a string (legacy path), serialize back
        # If dict (optimized path), leave as dict - caller will serialize once at the end
        if isinstance(attributes_val, str):
            span_data["Attributes"] = json.dumps(attributes)

        # Determine status based on error information
        error = attributes.get("error") or attributes.get("exception.message")
        status = self._determine_status(error)
        span_data["Status"] = status

    def _build_url(self, span_list: list[Dict[str, Any]]) -> str:
        """Construct the URL for the API request."""
        trace_id = str(span_list[0]["TraceId"])
        return f"{self.base_url}/llmopstenant_/api/Traces/spans?traceId={trace_id}&source=Robots"

    def _send_with_retries(
        self, url: str, payload: list[Dict[str, Any]], max_retries: int = 4
    ) -> SpanExportResult:
        """Send the HTTP request with retry logic."""
        for attempt in range(max_retries):
            try:
                response = self.http_client.post(url, json=payload)
                if response.status_code == 200:
                    return SpanExportResult.SUCCESS
                else:
                    logger.warning(
                        f"Attempt {attempt + 1} failed with status code {response.status_code}: {response.text}"
                    )
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed with exception: {e}")

            if attempt < max_retries - 1:
                time.sleep(1.5**attempt)  # Exponential backoff

        return SpanExportResult.FAILURE

    def _get_base_url(self) -> str:
        uipath_url = (
            os.environ.get("UIPATH_URL")
            or "https://cloud.uipath.com/dummyOrg/dummyTennant/"
        )

        uipath_url = uipath_url.rstrip("/")

        return uipath_url


class JsonLinesFileExporter(SpanExporter):
    def __init__(self, file_path: str):
        self.file_path = file_path
        # Ensure the directory exists
        dir_path = os.path.dirname(self.file_path)
        if dir_path:  # Only create if there's an actual directory path
            os.makedirs(dir_path, exist_ok=True)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            dict_spans = [span.to_json(indent=None) for span in spans]

            with open(self.file_path, "a") as f:
                for span in dict_spans:
                    f.write(span + "\n")
            return SpanExportResult.SUCCESS
        except Exception as e:
            logger.error(f"Failed to export spans to {self.file_path}: {e}")
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Shuts down the exporter."""
        pass
