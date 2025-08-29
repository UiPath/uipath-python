import json
import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult

from uipath.tracing._otel_exporters import (
    BaseSpanProcessor,
    JsonFileExporter,
    LlmOpsHttpExporter,
    SqliteExporter,
)


@pytest.fixture
def mock_env_vars():
    """Fixture to set and clean up environment variables for testing."""
    original_values = {}

    # Save original values
    for var in ["UIPATH_URL", "UIPATH_ACCESS_TOKEN"]:
        original_values[var] = os.environ.get(var)

    # Set test values
    os.environ["UIPATH_URL"] = "https://test.uipath.com/org/tenant/"
    os.environ["UIPATH_ACCESS_TOKEN"] = "test-token"

    yield

    # Restore original values
    for var, value in original_values.items():
        if value is None:
            if var in os.environ:
                del os.environ[var]
        else:
            os.environ[var] = value


@pytest.fixture
def mock_span():
    """Create a mock ReadableSpan for testing."""
    span = MagicMock(spec=ReadableSpan)
    return span


@pytest.fixture
def exporter(mock_env_vars):
    """Create an exporter instance for testing."""
    with patch("uipath.tracing._otel_exporters.httpx.Client"):
        exporter = LlmOpsHttpExporter()
        # Mock _build_url to include query parameters as in the actual implementation
        exporter._build_url = MagicMock(  # type: ignore
            return_value="https://test.uipath.com/org/tenant/llmopstenant_/api/Traces/spans?traceId=test-trace-id&source=Robots"
        )
        yield exporter


def test_init_with_env_vars(mock_env_vars):
    """Test initialization with environment variables."""
    with patch("uipath.tracing._otel_exporters.httpx.Client"):
        exporter = LlmOpsHttpExporter()

        assert exporter.base_url == "https://test.uipath.com/org/tenant"
        assert exporter.auth_token == "test-token"
        assert exporter.headers == {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-token",
        }


def test_init_with_default_url():
    """Test initialization with default URL when environment variable is not set."""
    with (
        patch("uipath.tracing._otel_exporters.httpx.Client"),
        patch.dict(os.environ, {"UIPATH_ACCESS_TOKEN": "test-token"}, clear=True),
    ):
        exporter = LlmOpsHttpExporter()

        assert exporter.base_url == "https://cloud.uipath.com/dummyOrg/dummyTennant"
        assert exporter.auth_token == "test-token"


def test_export_success(exporter, mock_span):
    """Test successful export of spans."""
    mock_uipath_span = MagicMock()
    mock_uipath_span.to_dict.return_value = {"span": "data", "TraceId": "test-trace-id"}

    with patch(
        "uipath.tracing._otel_exporters._SpanUtils.otel_span_to_uipath_span",
        return_value=mock_uipath_span,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 200
        exporter.http_client.post.return_value = mock_response

        result = exporter.export([mock_span])

        assert result == SpanExportResult.SUCCESS
        exporter._build_url.assert_called_once_with(
            [{"span": "data", "TraceId": "test-trace-id"}]
        )
        exporter.http_client.post.assert_called_once_with(
            "https://test.uipath.com/org/tenant/llmopstenant_/api/Traces/spans?traceId=test-trace-id&source=Robots",
            json=[{"span": "data", "TraceId": "test-trace-id"}],
        )


def test_export_failure(exporter, mock_span):
    """Test export failure with multiple retries."""
    mock_uipath_span = MagicMock()
    mock_uipath_span.to_dict.return_value = {"span": "data"}

    with patch(
        "uipath.tracing._otel_exporters._SpanUtils.otel_span_to_uipath_span",
        return_value=mock_uipath_span,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        exporter.http_client.post.return_value = mock_response

        with patch("uipath.tracing._otel_exporters.time.sleep") as mock_sleep:
            result = exporter.export([mock_span])

        assert result == SpanExportResult.FAILURE
        assert exporter.http_client.post.call_count == 4  # Default max_retries is 3
        assert (
            mock_sleep.call_count == 3
        )  # Should sleep between retries (except after the last one)


def test_export_exception(exporter, mock_span):
    """Test export with exceptions during HTTP request."""
    mock_uipath_span = MagicMock()
    mock_uipath_span.to_dict.return_value = {"span": "data"}

    with patch(
        "uipath.tracing._otel_exporters._SpanUtils.otel_span_to_uipath_span",
        return_value=mock_uipath_span,
    ):
        exporter.http_client.post.side_effect = Exception("Connection error")

        with patch("uipath.tracing._otel_exporters.time.sleep"):
            result = exporter.export([mock_span])

        assert result == SpanExportResult.FAILURE
        assert exporter.http_client.post.call_count == 4  # Default max_retries is 3


def test_force_flush(exporter):
    """Test force_flush returns True."""
    assert exporter.force_flush() is True


def test_get_base_url():
    """Test _get_base_url method with different environment configurations."""
    # Test with environment variable set
    with patch.dict(
        os.environ, {"UIPATH_URL": "https://custom.uipath.com/org/tenant/"}, clear=True
    ):
        with patch("uipath.tracing._otel_exporters.httpx.Client"):
            exporter = LlmOpsHttpExporter()
            assert exporter.base_url == "https://custom.uipath.com/org/tenant"

    # Test with environment variable set but with no trailing slash
    with patch.dict(
        os.environ, {"UIPATH_URL": "https://custom.uipath.com/org/tenant"}, clear=True
    ):
        with patch("uipath.tracing._otel_exporters.httpx.Client"):
            exporter = LlmOpsHttpExporter()
            assert exporter.base_url == "https://custom.uipath.com/org/tenant"

    # Test with no environment variable
    with patch.dict(os.environ, {}, clear=True):
        with patch("uipath.tracing._otel_exporters.httpx.Client"):
            exporter = LlmOpsHttpExporter()
            assert exporter.base_url == "https://cloud.uipath.com/dummyOrg/dummyTennant"


def test_send_with_retries_success():
    """Test _send_with_retries method with successful response."""
    with patch("uipath.tracing._otel_exporters.httpx.Client"):
        exporter = LlmOpsHttpExporter()

        mock_response = MagicMock()
        mock_response.status_code = 200
        exporter.http_client.post.return_value = mock_response  # type: ignore

        result = exporter._send_with_retries("http://example.com", [{"span": "data"}])

        assert result == SpanExportResult.SUCCESS
        exporter.http_client.post.assert_called_once_with(  # type: ignore
            "http://example.com", json=[{"span": "data"}]
        )


class MockSpanProcessor(BaseSpanProcessor):
    """Mock span processor for testing."""

    def process_span(self, span_data):
        """Process span by adding a test field."""
        processed = span_data.copy()
        processed["test_processed"] = True
        # Also add to attributes to test serialization
        if "attributes" not in processed:
            processed["attributes"] = {}
        if isinstance(processed["attributes"], dict):
            processed["attributes"]["test_processed"] = True
        return processed


@pytest.fixture
def mock_uipath_span():
    """Create a mock UiPath span for testing."""
    return {
        "TraceId": "test-trace-id",
        "SpanId": "test-span-id",
        "ParentSpanId": "test-parent-span-id",
        "Name": "test-span",
        "StartTime": "2023-01-01T00:00:00Z",
        "EndTime": "2023-01-01T00:01:00Z",
        "SpanType": "test",
        "attributes": {"key": "value"},
    }


@pytest.fixture
def mock_readable_span():
    """Create a mock ReadableSpan for testing."""
    span = MagicMock(spec=ReadableSpan)
    return span


class TestJsonFileExporter:
    """Test cases for JsonFileExporter."""

    def test_init_creates_directory(self):
        """Test that initialization creates the directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "subdir", "spans.jsonl")
            exporter = JsonFileExporter(file_path)

            assert os.path.exists(os.path.dirname(file_path))
            assert exporter.file_path == file_path

    def test_init_with_processor(self):
        """Test initialization with a span processor."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "spans.jsonl")
            processor = MockSpanProcessor()
            exporter = JsonFileExporter(file_path, processor)

            assert exporter.file_path == file_path
            assert exporter._processor == processor

    def test_export_uipath_spans_success(self, mock_uipath_span):
        """Test successful export of UiPath spans to JSON file."""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".jsonl"
        ) as temp_file:
            file_path = temp_file.name

        try:
            exporter = JsonFileExporter(file_path)
            result = exporter._export_uipath_spans([mock_uipath_span])

            assert result == SpanExportResult.SUCCESS

            # Verify file contents
            with open(file_path, "r") as f:
                lines = f.readlines()
                assert len(lines) == 1
                loaded_span = json.loads(lines[0].strip())
                assert loaded_span == mock_uipath_span
        finally:
            os.unlink(file_path)

    def test_export_uipath_spans_multiple(self, mock_uipath_span):
        """Test exporting multiple spans to JSON file."""
        span2 = mock_uipath_span.copy()
        span2["SpanId"] = "test-span-id-2"

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".jsonl"
        ) as temp_file:
            file_path = temp_file.name

        try:
            exporter = JsonFileExporter(file_path)
            result = exporter._export_uipath_spans([mock_uipath_span, span2])

            assert result == SpanExportResult.SUCCESS

            # Verify file contents
            with open(file_path, "r") as f:
                lines = f.readlines()
                assert len(lines) == 2
                assert json.loads(lines[0].strip()) == mock_uipath_span
                assert json.loads(lines[1].strip()) == span2
        finally:
            os.unlink(file_path)

    def test_export_uipath_spans_append(self, mock_uipath_span):
        """Test that spans are appended to existing file."""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".jsonl"
        ) as temp_file:
            file_path = temp_file.name
            # Write initial content
            temp_file.write(json.dumps({"initial": "span"}) + "\n")

        try:
            exporter = JsonFileExporter(file_path)
            result = exporter._export_uipath_spans([mock_uipath_span])

            assert result == SpanExportResult.SUCCESS

            # Verify file contents
            with open(file_path, "r") as f:
                lines = f.readlines()
                assert len(lines) == 2
                assert json.loads(lines[0].strip()) == {"initial": "span"}
                assert json.loads(lines[1].strip()) == mock_uipath_span
        finally:
            os.unlink(file_path)

    def test_export_with_processor(self, mock_readable_span, mock_uipath_span):
        """Test export with span processor integration."""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".jsonl"
        ) as temp_file:
            file_path = temp_file.name

        try:
            processor = MockSpanProcessor()
            exporter = JsonFileExporter(file_path, processor)

            with patch(
                "uipath.tracing._otel_exporters._SpanUtils.otel_span_to_uipath_span"
            ) as mock_converter:
                mock_uipath_span_obj = MagicMock()
                mock_uipath_span_obj.to_dict.return_value = mock_uipath_span
                mock_converter.return_value = mock_uipath_span_obj

                result = exporter.export([mock_readable_span])

            assert result == SpanExportResult.SUCCESS

            # Verify file contents include processor modification
            with open(file_path, "r") as f:
                lines = f.readlines()
                assert len(lines) == 1
                loaded_span = json.loads(lines[0].strip())
                assert loaded_span["test_processed"] is True
        finally:
            os.unlink(file_path)

    def test_export_uipath_spans_file_error(self):
        """Test export failure when file cannot be written."""
        # Use a Windows-specific invalid path
        import platform

        if platform.system() == "Windows":
            # Use an invalid character in filename
            invalid_path = "C:/invalid<>path/spans.jsonl"
        else:
            invalid_path = "/invalid/path/spans.jsonl"

        # Don't call constructor as it will try to create directories
        exporter = JsonFileExporter.__new__(JsonFileExporter)
        exporter.file_path = invalid_path
        exporter._processor = None

        result = exporter._export_uipath_spans([{"test": "span"}])
        assert result == SpanExportResult.FAILURE

    def test_shutdown(self):
        """Test shutdown method."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl") as temp_file:
            exporter = JsonFileExporter(temp_file.name)
            # Should not raise any exceptions
            exporter.shutdown()


class TestSqliteExporter:
    """Test cases for SqliteExporter."""

    def test_init_creates_directory_and_table(self):
        """Test that initialization creates directory and database table."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            # Create a path in a subdirectory that doesn't exist yet
            base_dir = os.path.dirname(temp_file.name)
            db_path = os.path.join(base_dir, "subdir", "spans.db")

        try:
            exporter = SqliteExporter(db_path)

            assert os.path.exists(os.path.dirname(db_path))
            assert os.path.exists(db_path)
            assert exporter.db_path == db_path

            # Verify table exists
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='spans'"
                )
                assert cursor.fetchone() is not None
        finally:
            try:
                os.unlink(db_path)
                os.rmdir(os.path.dirname(db_path))  # Remove the subdirectory
            except (PermissionError, FileNotFoundError, OSError):
                pass  # Ignore cleanup errors

    def test_init_with_processor(self):
        """Test initialization with a span processor."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "spans.db")
            processor = MockSpanProcessor()
            exporter = SqliteExporter(db_path, processor)

            assert exporter.db_path == db_path
            assert exporter._processor == processor

    def test_export_uipath_spans_success(self, mock_uipath_span):
        """Test successful export of UiPath spans to SQLite database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            db_path = temp_file.name

        try:
            exporter = SqliteExporter(db_path)
            result = exporter._export_uipath_spans([mock_uipath_span])

            assert result == SpanExportResult.SUCCESS

            # Verify database contents
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM spans")
                rows = cursor.fetchall()
                assert len(rows) == 1

                row = rows[0]
                assert row[1] == mock_uipath_span["TraceId"]  # trace_id
                assert row[2] == mock_uipath_span["SpanId"]  # span_id
                assert row[3] == mock_uipath_span["ParentSpanId"]  # parent_span_id
                assert row[4] == mock_uipath_span["Name"]  # name
                assert row[5] == mock_uipath_span["StartTime"]  # start_time
                assert row[6] == mock_uipath_span["EndTime"]  # end_time
                assert row[7] == mock_uipath_span["SpanType"]  # span_type
                assert (
                    json.loads(row[8]) == mock_uipath_span["attributes"]
                )  # attributes
        finally:
            try:
                os.unlink(db_path)
            except (PermissionError, FileNotFoundError):
                pass  # Ignore cleanup errors on Windows

    def test_export_uipath_spans_multiple(self, mock_uipath_span):
        """Test exporting multiple spans to SQLite database."""
        span2 = mock_uipath_span.copy()
        span2["SpanId"] = "test-span-id-2"

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            db_path = temp_file.name

        try:
            exporter = SqliteExporter(db_path)
            result = exporter._export_uipath_spans([mock_uipath_span, span2])

            assert result == SpanExportResult.SUCCESS

            # Verify database contents
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT span_id FROM spans ORDER BY id")
                rows = cursor.fetchall()
                assert len(rows) == 2
                assert rows[0][0] == mock_uipath_span["SpanId"]
                assert rows[1][0] == span2["SpanId"]
        finally:
            try:
                os.unlink(db_path)
            except (PermissionError, FileNotFoundError):
                pass  # Ignore cleanup errors on Windows

    def test_export_uipath_spans_attributes_serialization(self):
        """Test that complex attributes are properly serialized."""
        span_with_complex_attrs = {
            "TraceId": "test-trace-id",
            "SpanId": "test-span-id",
            "ParentSpanId": None,
            "Name": "test-span",
            "StartTime": "2023-01-01T00:00:00Z",
            "EndTime": "2023-01-01T00:01:00Z",
            "SpanType": "test",
            "attributes": {"nested": {"key": "value"}, "list": [1, 2, 3]},
        }

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            db_path = temp_file.name

        try:
            exporter = SqliteExporter(db_path)
            result = exporter._export_uipath_spans([span_with_complex_attrs])

            assert result == SpanExportResult.SUCCESS

            # Verify attributes serialization
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT attributes FROM spans")
                row = cursor.fetchone()
                stored_attrs = json.loads(row[0])
                assert stored_attrs == span_with_complex_attrs["attributes"]
        finally:
            try:
                os.unlink(db_path)
            except (PermissionError, FileNotFoundError):
                pass  # Ignore cleanup errors on Windows

    def test_export_with_processor(self, mock_readable_span, mock_uipath_span):
        """Test export with span processor integration."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            db_path = temp_file.name

        try:
            processor = MockSpanProcessor()
            exporter = SqliteExporter(db_path, processor)

            with patch(
                "uipath.tracing._otel_exporters._SpanUtils.otel_span_to_uipath_span"
            ) as mock_converter:
                mock_uipath_span_obj = MagicMock()
                mock_uipath_span_obj.to_dict.return_value = mock_uipath_span
                mock_converter.return_value = mock_uipath_span_obj

                result = exporter.export([mock_readable_span])

            assert result == SpanExportResult.SUCCESS

            # Verify processor was applied
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT attributes FROM spans")
                row = cursor.fetchone()
                stored_attrs = json.loads(row[0])
                # MockSpanProcessor adds test_processed field to attributes
                assert "test_processed" in stored_attrs
                assert stored_attrs["test_processed"] is True
        finally:
            try:
                os.unlink(db_path)
            except (PermissionError, FileNotFoundError):
                pass  # Ignore cleanup errors on Windows

    def test_export_uipath_spans_database_error(self):
        """Test export failure when database cannot be accessed."""
        # Use an invalid path that will cause a database error
        invalid_path = "/invalid/path/spans.db"
        exporter = SqliteExporter.__new__(SqliteExporter)  # Skip __init__
        exporter.db_path = invalid_path
        exporter._processor = None

        result = exporter._export_uipath_spans([{"test": "span"}])
        assert result == SpanExportResult.FAILURE

    def test_shutdown(self):
        """Test shutdown method."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            db_path = temp_file.name

        try:
            exporter = SqliteExporter(db_path)
            # Should not raise any exceptions
            exporter.shutdown()
        finally:
            try:
                os.unlink(db_path)
            except (PermissionError, FileNotFoundError):
                pass  # Ignore cleanup errors on Windows

    def test_create_table_idempotent(self):
        """Test that _create_table can be called multiple times safely."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            db_path = temp_file.name

        try:
            exporter = SqliteExporter(db_path)
            # Call _create_table again - should not raise an error
            exporter._create_table()

            # Verify table still exists and is functional
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='spans'"
                )
                assert cursor.fetchone() is not None
        finally:
            try:
                os.unlink(db_path)
            except (PermissionError, FileNotFoundError):
                pass  # Ignore cleanup errors on Windows

    def test_metadata_table_creation(self):
        """Test that metadata table is created during initialization."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            db_path = temp_file.name

        try:
            exporter = SqliteExporter(db_path)

            # Verify metadata table exists
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='__uipath_meta'"
                )
                assert cursor.fetchone() is not None

                # Verify schema version was set
                cursor.execute(
                    "SELECT value FROM __uipath_meta WHERE key = 'schema_version'"
                )
                version = cursor.fetchone()
                assert version is not None
                assert version[0] == SqliteExporter.SCHEMA_VERSION
        finally:
            try:
                os.unlink(db_path)
            except (PermissionError, FileNotFoundError):
                pass

    def test_get_schema_version(self):
        """Test getting the schema version."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            db_path = temp_file.name

        try:
            exporter = SqliteExporter(db_path)
            version = exporter.get_schema_version()
            assert version == SqliteExporter.SCHEMA_VERSION
        finally:
            try:
                os.unlink(db_path)
            except (PermissionError, FileNotFoundError):
                pass

    def test_get_schema_version_nonexistent_db(self):
        """Test getting schema version from non-existent database."""
        invalid_path = "/invalid/path/nonexistent.db"
        exporter = SqliteExporter.__new__(SqliteExporter)  # Skip __init__
        exporter.db_path = invalid_path

        version = exporter.get_schema_version()
        assert version is None

    def test_metadata_operations(self):
        """Test setting, getting, and listing metadata."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            db_path = temp_file.name

        try:
            exporter = SqliteExporter(db_path)

            # Test setting metadata
            assert exporter.set_metadata("test_key", "test_value") is True
            assert exporter.set_metadata("another_key", "another_value") is True

            # Test getting metadata
            assert exporter.get_metadata("test_key") == "test_value"
            assert exporter.get_metadata("another_key") == "another_value"
            assert exporter.get_metadata("nonexistent_key") is None

            # Test updating existing metadata
            assert exporter.set_metadata("test_key", "updated_value") is True
            assert exporter.get_metadata("test_key") == "updated_value"

            # Test listing metadata
            metadata = exporter.list_metadata()
            assert "test_key" in metadata
            assert "another_key" in metadata
            assert "schema_version" in metadata
            assert "created_by" in metadata
            assert "exporter_class" in metadata

            assert metadata["test_key"]["value"] == "updated_value"
            assert metadata["another_key"]["value"] == "another_value"
            assert "created_at" in metadata["test_key"]
            assert "updated_at" in metadata["test_key"]
        finally:
            try:
                os.unlink(db_path)
            except (PermissionError, FileNotFoundError):
                pass

    def test_metadata_operations_with_database_errors(self):
        """Test metadata operations with database errors."""
        invalid_path = "/invalid/path/nonexistent.db"
        exporter = SqliteExporter.__new__(SqliteExporter)  # Skip __init__
        exporter.db_path = invalid_path

        # Test operations with invalid database
        assert exporter.get_metadata("test_key") is None
        assert exporter.set_metadata("test_key", "test_value") is False
        assert exporter.list_metadata() == {}

    def test_schema_version_update(self):
        """Test schema version update when version changes."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            db_path = temp_file.name

        try:
            # Create database with initial version
            exporter1 = SqliteExporter(db_path)
            initial_version = exporter1.get_schema_version()
            assert initial_version == SqliteExporter.SCHEMA_VERSION

            # Manually update the version in the database to simulate an older version
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE __uipath_meta SET value = ? WHERE key = 'schema_version'",
                    ("0.9.0",),
                )
                conn.commit()

            # Verify the old version is stored
            assert exporter1.get_schema_version() == "0.9.0"

            # Create a new exporter instance - should update the version
            exporter2 = SqliteExporter(db_path)
            updated_version = exporter2.get_schema_version()
            assert updated_version == SqliteExporter.SCHEMA_VERSION
        finally:
            try:
                os.unlink(db_path)
            except (PermissionError, FileNotFoundError):
                pass

    def test_default_metadata_entries(self):
        """Test that default metadata entries are created."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            db_path = temp_file.name

        try:
            exporter = SqliteExporter(db_path)
            metadata = exporter.list_metadata()

            # Check default entries
            assert metadata["schema_version"]["value"] == SqliteExporter.SCHEMA_VERSION
            assert metadata["created_by"]["value"] == "UiPath SQLiteExporter"
            assert metadata["exporter_class"]["value"] == "SqliteExporter"

            # Check that timestamps are present
            for key in ["schema_version", "created_by", "exporter_class"]:
                assert "created_at" in metadata[key]
                assert "updated_at" in metadata[key]
                # Basic timestamp format check (ISO format)
                assert "T" in metadata[key]["created_at"]
                assert metadata[key]["created_at"].endswith("Z")
        finally:
            try:
                os.unlink(db_path)
            except (PermissionError, FileNotFoundError):
                pass
