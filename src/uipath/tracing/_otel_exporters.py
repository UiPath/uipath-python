import json
import logging
import os
import sqlite3
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, MutableMapping, Sequence

import httpx
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)
from typing_extensions import override

from uipath._utils._ssl_context import get_httpx_client_kwargs

from ._utils import _SpanUtils

logger = logging.getLogger(__name__)


class LlmOpsHttpExporter(SpanExporter):
    """An OpenTelemetry span exporter that sends spans to UiPath LLM Ops."""

    def __init__(self, **client_kwargs):
        """Initialize the exporter with the base URL and authentication token."""
        super().__init__(**client_kwargs)
        self.base_url = self._get_base_url()
        self.auth_token = os.environ.get("UIPATH_ACCESS_TOKEN")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
        }

        client_kwargs = get_httpx_client_kwargs()

        self.http_client = httpx.Client(**client_kwargs, headers=self.headers)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export spans to UiPath LLM Ops."""
        logger.debug(
            f"Exporting {len(spans)} spans to {self.base_url}/llmopstenant_/api/Traces/spans"
        )

        span_list = [
            _SpanUtils.otel_span_to_uipath_span(span).to_dict() for span in spans
        ]
        url = self._build_url(span_list)

        logger.debug("Payload: %s", json.dumps(span_list))

        return self._send_with_retries(url, span_list)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush the exporter."""
        return True

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


class BaseSpanProcessor(ABC):
    """Abstract base class for span processors.

    Defines the interface for processing spans with a single abstract method.
    """

    def __init__(
        self,
        dump_attributes_as_string: bool = True,
        unflatten_attributes: bool = True,
        map_json_fields: bool = True,
    ):
        self._dump_attributes_as_string = dump_attributes_as_string
        self._unflatten_attributes = unflatten_attributes
        self._map_json_fields = map_json_fields

    def try_convert_json(self, flat_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Tries to convert stringified JSON values in a flattened dictionary back to their original types.

        Args:
            flat_dict: A dictionary with potentially stringified JSON values.

        Returns:
            A new dictionary with JSON strings converted to their original types.
        """
        result = {}
        for key, value in flat_dict.items():
            if isinstance(value, str):
                try:
                    result[key] = json.loads(value)
                except json.JSONDecodeError:
                    result[key] = value
            else:
                result[key] = value
        return result

    def unflatten_dict(self, flat_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Converts a flattened dictionary with dot-separated keys into a nested dictionary.

        Args:
            flat_dict: Dictionary with dot-separated keys (e.g., 'llm.output_messages.0.message.content')

        Returns:
            Nested dictionary structure

        Example:
            Input: {'llm.output_messages.0.message.content': 'hello', 'llm.model': 'gpt-4'}
            Output: {'llm': {'output_messages': [{'message': {'content': 'hello'}}], 'model': 'gpt-4'}}
        """
        result = {}

        for key, value in flat_dict.items():
            # Split the key by dots
            parts = key.split(".")
            current = result

            # Navigate/create the nested structure
            for i, part in enumerate(parts[:-1]):
                # Check if this part represents an array index
                if part.isdigit():
                    # Convert to integer index
                    index = int(part)
                    # Ensure the parent is a list
                    if not isinstance(current, list):
                        raise ValueError(
                            f"Expected list but found {type(current)} for key: {key}"
                        )
                    # Extend the list if necessary
                    while len(current) <= index:
                        current.append(None)

                    # If the current element is None, we need to create a structure for it
                    if current[index] is None:
                        # Look ahead to see if the next part is a digit (array index)
                        next_part = parts[i + 1] if i + 1 < len(parts) else None
                        if next_part and next_part.isdigit():
                            current[index] = []
                        else:
                            current[index] = {}

                    current = current[index]
                else:
                    # Regular dictionary key
                    if part not in current:
                        # Look ahead to see if the next part is a digit (array index)
                        next_part = parts[i + 1] if i + 1 < len(parts) else None
                        if next_part and next_part.isdigit():
                            current[part] = []
                        else:
                            current[part] = {}
                    current = current[part]  # Set the final value

            final_key = parts[-1]
            if final_key.isdigit():
                # If the final key is a digit, we're setting an array element
                index = int(final_key)
                if not isinstance(current, list):
                    raise ValueError(
                        f"Expected list but found {type(current)} for key: {key}"
                    )
                while len(current) <= index:
                    current.append(None)
                current[index] = value
            else:
                # Regular key assignment
                current[final_key] = value

        return result

    def safe_get(self, data: Dict[str, Any], path: str, default=None):
        """Safely get nested value using dot notation."""
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current

    def safe_parse_json(self, value):
        """Safely parse JSON string."""
        if isinstance(value, str):
            try:
                return json.loads(value.replace("'", '"'))
            except json.JSONDecodeError:
                return value
        return value

    @abstractmethod
    def process_span(self, span_data: MutableMapping[str, Any]) -> Dict[str, Any]:
        return span_data


class CommonSpanProcessor(BaseSpanProcessor):
    """A class to process spans, applying custom attribute and type mappings.

    This processor can transform flattened attribute keys (e.g., 'llm.output_messages.0.message.role')
    into nested dictionary structures for easier access and processing.

    Example usage:
        # With unflattening enabled
        processor = LangchainSpanProcessor(unflatten_attributes=True, dump_attributes_as_string=False)
        processed_span = processor.process_span(span_data)

        # Access nested attributes naturally:
        role = processed_span['attributes']['llm']['output_messages'][0]['message']['role']

        # Without unflattening (original behavior)
        processor = LangchainSpanProcessor(unflatten_attributes=False)
        processed_span = processor.process_span(span_data)

        # Access with flattened keys:
        role = processed_span['attributes']['llm.output_messages.0.message.role']
    """

    # Mapping of old attribute names to new attribute names or (new name, function)
    ATTRIBUTE_MAPPING = {
        "input.value": ("input", lambda s: json.loads(s)),
        "output.value": ("output", lambda s: json.loads(s)),
        "llm.model_name": "model",
    }

    # Mapping of span types
    SPAN_TYPE_MAPPING = {
        "LLM": "completion",
        "TOOL": "toolCall",
        # Add more mappings as needed
    }

    def __init__(
        self,
        dump_attributes_as_string: bool = True,
        unflatten_attributes: bool = True,
        map_json_fields: bool = True,
    ):
        """Initializes the LangchainSpanProcessor.

        Args:
            dump_attributes_as_string: If True, dumps attributes as a JSON string.
                                       Otherwise, attributes are set as a dictionary.
            unflatten_attributes: If True, converts flattened dot-separated keys
                                  into nested dictionary structures.
            map_json_fields: If True, applies JSON field mapping transformations
                            for tool calls and LLM calls.
        """
        self._dump_attributes_as_string = dump_attributes_as_string
        self._unflatten_attributes = unflatten_attributes
        self._map_json_fields = map_json_fields

    def extract_attributes(self, span_data: MutableMapping[str, Any]) -> Dict[str, Any]:
        """Extract and parse attributes from span_data, checking both 'Attributes' and 'attributes' keys."""
        for key in ["Attributes", "attributes"]:
            if key in span_data:
                value = span_data.pop(key)
                if isinstance(value, str):
                    try:
                        parsed_value = json.loads(value)
                        return parsed_value if isinstance(parsed_value, dict) else {}
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse attributes JSON: {value}")
                        return {}
                elif isinstance(value, dict):
                    return value
                else:
                    return {}
        return {}

    @override
    def process_span(self, span_data: MutableMapping[str, Any]) -> Dict[str, Any]:
        logger.info(f"Processing span: {span_data}")
        attributes = self.extract_attributes(span_data)

        if attributes and isinstance(attributes, dict):
            if "openinference.span.kind" in attributes:
                # Remove the span kind attribute
                span_type = attributes["openinference.span.kind"]
                # Map span type using SPAN_TYPE_MAPPING
                span_data["SpanType"] = self.SPAN_TYPE_MAPPING.get(span_type, span_type)
                del attributes["openinference.span.kind"]

            # Apply the transformation logic
            for old_key, mapping in self.ATTRIBUTE_MAPPING.items():
                if old_key in attributes:
                    if isinstance(mapping, tuple):
                        new_key, func = mapping
                        try:
                            attributes[new_key] = func(attributes[old_key])
                        except Exception:
                            attributes[new_key] = attributes[old_key]
                    else:
                        new_key = mapping
                        attributes[new_key] = attributes[old_key]
                    del attributes[old_key]

        if attributes:
            # Apply unflattening if requested (before JSON field mapping)
            if self._unflatten_attributes:
                try:
                    attributes = self.try_convert_json(attributes)
                    attributes = self.unflatten_dict(attributes)
                except Exception as e:
                    logger.warning(f"Failed to unflatten attributes: {e}")

            # Set attributes in span_data as dictionary for JSON field mapping
            span_data["attributes"] = attributes

            # Apply JSON field mapping before final serialization
            if self._map_json_fields:
                span_data = self.map_json_fields_from_attributes(span_data)

            # Convert back to JSON string if requested (after all transformations)
            if self._dump_attributes_as_string:
                span_data["attributes"] = json.dumps(span_data["attributes"])

        return span_data

    def map_tool_call_attributes(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Simple tool call mapping - just add new fields."""
        result = attributes.copy()  # Keep originals

        # Add new fields
        result["type"] = "toolCall"
        result["callId"] = attributes.get("call_id") or attributes.get("id")
        result["toolName"] = self.safe_get(attributes, "tool.name")
        result["arguments"] = self.safe_parse_json(attributes.get("input", "{}"))
        result["toolType"] = "Integration"
        result["result"] = self.safe_parse_json(attributes.get("output"))
        result["error"] = None

        return result

    def map_llm_call_attributes(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        """Simple LLM call mapping - just add new fields."""
        result = attributes.copy()  # Keep originals

        # Transform token usage data if present (after unflattening)
        # Use safe_get to extract token count values from nested structure
        prompt_tokens = self.safe_get(attributes, "llm.token_count.prompt")
        completion_tokens = self.safe_get(attributes, "llm.token_count.completion")
        total_tokens = self.safe_get(attributes, "llm.token_count.total")

        usage = {
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": total_tokens,
            "isByoExecution": False,
            "executionDeploymentType": "PAYGO",
            "isPiiMasked": False,
        }

        # remove None values
        usage = {k: v for k, v in usage.items() if v is not None}

        result["usage"] = usage

        # Add new fields
        result["input"] = self.safe_get(attributes, "llm.input_messages")
        result["output"] = self.safe_get(attributes, "llm.output_messages")

        result["type"] = "completion"
        result["model"] = self.safe_get(attributes, "llm.invocation_parameters.model")

        # Settings
        settings = {}
        max_tokens = self.safe_get(attributes, "llm.invocation_parameters.max_tokens")
        temperature = self.safe_get(attributes, "llm.invocation_parameters.temperature")
        if max_tokens:
            settings["maxTokens"] = max_tokens
        if temperature is not None:
            settings["temperature"] = temperature
        if settings:
            result["settings"] = settings

        # Tool calls (simplified)
        tool_calls = []
        output_msgs = self.safe_get(attributes, "llm.output_messages", [])
        for msg in output_msgs:
            msg_tool_calls = self.safe_get(msg, "message.tool_calls", [])
            for tc in msg_tool_calls:
                tool_call_data = tc.get("tool_call", {})
                tool_calls.append(
                    {
                        "id": tool_call_data.get("id"),
                        "name": self.safe_get(tool_call_data, "function.name"),
                        "arguments": self.safe_get(
                            tool_call_data, "function.arguments", {}
                        ),
                    }
                )
        if tool_calls:
            result["toolCalls"] = tool_calls

        # Usage (enhance existing if not created above)
        if "usage" in result:
            usage = result["usage"]
            if isinstance(usage, dict):
                usage.setdefault("isByoExecution", False)
                usage.setdefault("executionDeploymentType", "PAYGO")
                usage.setdefault("isPiiMasked", False)

        return result

    def map_json_fields_from_attributes(
        self, span_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simple mapping dispatcher."""
        if "attributes" not in span_data:
            return span_data

        attributes = span_data["attributes"]

        # Parse if string
        if isinstance(attributes, str):
            try:
                attributes = json.loads(attributes)
            except json.JSONDecodeError:
                return span_data

        if not isinstance(attributes, dict):
            return span_data

        # Simple detection and mapping
        if "tool" in attributes or span_data.get("SpanType") == "toolCall":
            span_data["attributes"] = self.map_tool_call_attributes(attributes)
        elif "llm" in attributes or span_data.get("SpanType") == "completion":
            span_data["attributes"] = self.map_llm_call_attributes(attributes)

        return span_data


class UiPathSpanExporterBase(SpanExporter, ABC):
    """Base class for UiPath span exporters."""

    def __init__(
        self, processor: BaseSpanProcessor | None = None, *args: Any, **kwargs: Any
    ) -> None:
        """Initializes the exporter with an optional span processor."""
        super().__init__(*args, **kwargs)
        self._processor = processor

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Converts and exports spans.

        This method converts OpenTelemetry ReadableSpan objects to the UiPath
        span format and then calls the subclass's implementation of
        _export_uipath_spans.
        """
        if not spans:
            return SpanExportResult.SUCCESS
        try:
            uipath_spans = [
                _SpanUtils.otel_span_to_uipath_span(span).to_dict() for span in spans
            ]

            processed_spans = uipath_spans

            if self._processor:
                processed_spans = [
                    self._processor.process_span(span) for span in uipath_spans
                ]

            return self._export_uipath_spans(processed_spans)
        except Exception as e:
            logger.error(f"Failed to export spans: {e}", exc_info=True)
            return SpanExportResult.FAILURE

    @abstractmethod
    def _export_uipath_spans(
        self, uipath_spans: list[Dict[str, Any]]
    ) -> SpanExportResult:
        """Exports a list of spans in UiPath format.

        Subclasses must implement this method to define the export mechanism
        (e.g., sending over HTTP, writing to a file).

        Args:
            uipath_spans: A list of spans, each represented as a dictionary.

        Returns:
            The result of the export operation.
        """
        raise NotImplementedError


class JsonFileExporter(UiPathSpanExporterBase):
    """An exporter that writes spans to a file in JSON Lines format.

    This exporter is useful for debugging and local development. It serializes
    each span to a JSON object and appends it as a new line in the specified
    file.
    """

    def __init__(self, file_path: str, processor: BaseSpanProcessor | None = None):
        """Initializes the JsonFileExporter.

        Args:
            file_path: The path to the JSON file where spans will be written.
            processor: Optional span processor for transforming spans.
        """
        super().__init__(processor)
        self.file_path = file_path
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def _export_uipath_spans(
        self, uipath_spans: list[Dict[str, Any]]
    ) -> SpanExportResult:
        """Exports UiPath spans to a JSON file.

        Args:
            uipath_spans: A list of spans in UiPath format.

        Returns:
            The result of the export operation.
        """
        try:
            with open(self.file_path, "a") as f:
                for span in uipath_spans:
                    f.write(json.dumps(span) + "\n")
            return SpanExportResult.SUCCESS
        except Exception as e:
            logger.error(f"Failed to export spans to {self.file_path}: {e}")
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Shuts down the exporter."""
        pass


class SqliteExporter(UiPathSpanExporterBase):
    """An exporter that writes spans to a SQLite database file.

    This exporter is useful for debugging and local development. It serializes
    the spans and inserts them into a 'spans' table in the specified database.
    """

    # Schema version for the SQLite database
    SCHEMA_VERSION = "1.0.0"

    def __init__(self, db_path: str, processor: BaseSpanProcessor | None = None):
        """Initializes the SqliteExporter.

        Args:
            db_path: The path to the SQLite database file.
            processor: Optional span processor for transforming spans.
        """
        super().__init__(processor)
        self.db_path = db_path
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._create_tables()

    def _create_tables(self):
        """Creates the necessary tables if they don't already exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create metadata table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS __uipath_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # Create spans table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS spans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT,
                    span_id TEXT,
                    parent_span_id TEXT,
                    name TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    span_type TEXT,
                    attributes TEXT
                )
            """
            )

            # Initialize or update schema version
            self._initialize_metadata(cursor)
            conn.commit()

    def _initialize_metadata(self, cursor: sqlite3.Cursor):
        """Initialize or update metadata in the database.

        Args:
            cursor: The SQLite cursor to use for database operations.
        """
        import datetime

        current_time = (
            datetime.datetime.now(datetime.timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )  # Check if schema_version already exists
        cursor.execute("SELECT value FROM __uipath_meta WHERE key = 'schema_version'")
        existing_version = cursor.fetchone()

        if existing_version:
            # Update existing version if different
            if existing_version[0] != self.SCHEMA_VERSION:
                cursor.execute(
                    """
                    UPDATE __uipath_meta 
                    SET value = ?, updated_at = ? 
                    WHERE key = 'schema_version'
                    """,
                    (self.SCHEMA_VERSION, current_time),
                )
                logger.info(
                    f"Updated schema version from {existing_version[0]} to {self.SCHEMA_VERSION}"
                )
        else:
            # Insert new metadata entries
            metadata_entries = [
                ("schema_version", self.SCHEMA_VERSION, current_time, current_time),
                ("created_by", "UiPath SQLiteExporter", current_time, current_time),
                ("exporter_class", self.__class__.__name__, current_time, current_time),
            ]

            cursor.executemany(
                """
                INSERT INTO __uipath_meta (key, value, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                metadata_entries,
            )
            logger.info(
                f"Initialized database with schema version {self.SCHEMA_VERSION}"
            )

    def get_schema_version(self) -> str | None:
        """Get the current schema version from the database.

        Returns:
            The schema version string, or None if not found.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT value FROM __uipath_meta WHERE key = 'schema_version'"
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except (sqlite3.Error, Exception) as e:
            logger.warning(f"Failed to get schema version: {e}")
            return None

    def get_metadata(self, key: str) -> str | None:
        """Get a metadata value by key.

        Args:
            key: The metadata key to retrieve.

        Returns:
            The metadata value, or None if not found.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM __uipath_meta WHERE key = ?", (key,))
                result = cursor.fetchone()
                return result[0] if result else None
        except (sqlite3.Error, Exception) as e:
            logger.warning(f"Failed to get metadata for key '{key}': {e}")
            return None

    def set_metadata(self, key: str, value: str) -> bool:
        """Set a metadata key-value pair.

        Args:
            key: The metadata key.
            value: The metadata value.

        Returns:
            True if successful, False otherwise.
        """
        try:
            import datetime

            current_time = (
                datetime.datetime.now(datetime.timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO __uipath_meta (key, value, created_at, updated_at)
                    VALUES (
                        ?, ?, 
                        COALESCE((SELECT created_at FROM __uipath_meta WHERE key = ?), ?),
                        ?
                    )
                    """,
                    (key, value, key, current_time, current_time),
                )
                conn.commit()
                return True
        except (sqlite3.Error, Exception) as e:
            logger.error(f"Failed to set metadata for key '{key}': {e}")
            return False

    def list_metadata(self) -> Dict[str, Dict[str, str]]:
        """List all metadata entries.

        Returns:
            A dictionary mapping keys to metadata information including value and timestamps.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT key, value, created_at, updated_at FROM __uipath_meta ORDER BY key"
                )
                results = cursor.fetchall()

                return {
                    row[0]: {
                        "value": row[1],
                        "created_at": row[2],
                        "updated_at": row[3],
                    }
                    for row in results
                }
        except (sqlite3.Error, Exception) as e:
            logger.warning(f"Failed to list metadata: {e}")
            return {}

    def _create_table(self):
        """Legacy method for backward compatibility. Use _create_tables instead."""
        self._create_tables()

    def _export_uipath_spans(
        self, uipath_spans: list[Dict[str, Any]]
    ) -> SpanExportResult:
        """Exports UiPath spans to a SQLite database.

        Args:
            uipath_spans: A list of spans in UiPath format.

        Returns:
            The result of the export operation.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for span in uipath_spans:
                    # The 'attributes' field is a JSON string, so we store it as TEXT.
                    attributes_json = span.get("attributes", "{}")
                    if not isinstance(attributes_json, str):
                        attributes_json = json.dumps(attributes_json)

                    cursor.execute(
                        """
                        INSERT INTO spans (
                            trace_id, span_id, parent_span_id, name,
                            start_time, end_time, span_type, attributes
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            span.get("TraceId"),
                            span.get("SpanId"),
                            span.get("ParentSpanId"),
                            span.get("Name"),
                            span.get("StartTime"),
                            span.get("EndTime"),
                            span.get("SpanType"),
                            attributes_json,
                        ),
                    )
                conn.commit()

            return SpanExportResult.SUCCESS
        except Exception as e:
            logger.error(f"Failed to export spans to {self.db_path}: {e}")
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:
        """Shuts down the exporter."""
        pass
