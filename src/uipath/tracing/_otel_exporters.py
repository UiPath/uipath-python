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

    @abstractmethod
    def process_span(self, span_data: MutableMapping[str, Any]) -> Dict[str, Any]:
        """Process a span and return the transformed data.

        Args:
            span_data: The span data to process

        Returns:
            Processed span data
        """
        pass


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
