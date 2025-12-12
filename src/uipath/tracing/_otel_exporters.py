import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Sequence

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
        **kwargs,
    ):
        """Initialize the exporter with the base URL and authentication token."""
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

        # Track filtered root span IDs across export batches for reparenting
        # Maps original parent ID -> new parent ID for reparenting
        self._parent_id_mapping: dict[str, str] = {}

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

        # Filter out root span and reparent children if UIPATH_FILTER_PARENT_SPAN is set
        filter_parent_span = os.environ.get("UIPATH_FILTER_PARENT_SPAN")
        parent_span_id = os.environ.get("UIPATH_PARENT_SPAN_ID")
        if filter_parent_span and parent_span_id:
            span_list = self._filter_root_and_reparent(span_list, parent_span_id)

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

    def _filter_root_and_reparent(
        self, span_list: List[Dict[str, Any]], new_parent_id: str
    ) -> List[Dict[str, Any]]:
        """Filter out root spans and reparent their children to the new parent ID.

        Maintains a persistent mapping of filtered span IDs to their replacement parent IDs
        to handle cases where child spans arrive in later batches than their parents.

        Args:
            span_list: List of span dictionaries
            new_parent_id: The new parent span ID for orphaned children

        Returns:
            Filtered list of spans with updated parent IDs
        """
        logger.info(
            f"_filter_root_and_reparent called with {len(span_list)} spans, "
            f"new_parent_id={new_parent_id}, "
            f"existing mapping keys: {list(self._parent_id_mapping.keys())}"
        )

        # First pass: Find all root span IDs in this batch and build the mapping
        for span in span_list:
            attributes = span.get("Attributes", {})
            is_root = isinstance(attributes, dict) and attributes.get("uipath.root_span")
            logger.info(
                f"Pass 1 - Checking span: Id={span.get('Id')}, Name={span.get('Name')}, "
                f"ParentId={span.get('ParentId')}, is_root={is_root}, "
                f"attributes type={type(attributes).__name__}"
            )
            if is_root:
                self._parent_id_mapping[span["Id"]] = new_parent_id
                logger.info(
                    f"Added root span to mapping: {span['Id']} -> {new_parent_id}"
                )

        logger.info(f"After pass 1, mapping: {self._parent_id_mapping}")

        # Build set of span IDs in this batch
        batch_span_ids = {span["Id"] for span in span_list}

        # Second pass: Filter out root spans and reparent children
        filtered_spans = []
        for span in span_list:
            span_id = span["Id"]
            parent_id = span.get("ParentId")

            # Skip root spans (they are in the mapping)
            if span_id in self._parent_id_mapping:
                logger.info(f"Pass 2 - Filtering out root span: Id={span_id}, Name={span.get('Name')}")
                continue

            # Reparent spans whose parent was filtered (is in the mapping)
            if parent_id and parent_id in self._parent_id_mapping:
                old_parent = parent_id
                span["ParentId"] = self._parent_id_mapping[parent_id]
                logger.info(
                    f"Pass 2 - Reparented span: Id={span_id}, Name={span.get('Name')}, "
                    f"old ParentId={old_parent} -> new ParentId={span['ParentId']}"
                )
            # Reparent orphan spans whose parent is not in batch, not in mapping, and not the new_parent_id
            elif parent_id and parent_id not in batch_span_ids and parent_id != new_parent_id:
                old_parent = parent_id
                span["ParentId"] = new_parent_id
                # Add to mapping so future spans with same parent get reparented
                self._parent_id_mapping[parent_id] = new_parent_id
                logger.info(
                    f"Pass 2 - Reparented orphan span: Id={span_id}, Name={span.get('Name')}, "
                    f"old ParentId={old_parent} -> new ParentId={new_parent_id} (parent not in batch)"
                )
            else:
                logger.info(
                    f"Pass 2 - Keeping span unchanged: Id={span_id}, Name={span.get('Name')}, "
                    f"ParentId={parent_id}, in_mapping={parent_id in self._parent_id_mapping if parent_id else 'N/A'}"
                )

            filtered_spans.append(span)

        logger.info(
            f"Filtering complete: {len(span_list)} -> {len(filtered_spans)} spans"
        )
        return filtered_spans

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
