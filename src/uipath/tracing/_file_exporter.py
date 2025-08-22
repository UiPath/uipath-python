import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, List, Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)

from uipath.tracing._models import Status, UiPathEvalSpan

from ._utils import UiPathSpan, _SpanUtils

logger = logging.getLogger(__name__)


def _deserialize_span_dict(span_dict: dict[str, Any]) -> dict[str, Any]:
    """Deserialize ISO format strings back to datetime objects.

    Args:
        span_dict: Dictionary with ISO format datetime strings.

    Returns:
        Dictionary with datetime strings converted back to datetime objects.
    """
    deserialized_dict = span_dict.copy()
    # Convert ISO format strings back to datetime objects for known datetime fields
    datetime_fields = ["start_time", "end_time"]
    for field in datetime_fields:
        if field in deserialized_dict and isinstance(deserialized_dict[field], str):
            try:
                deserialized_dict[field] = datetime.fromisoformat(
                    deserialized_dict[field]
                )
            except ValueError:
                # If parsing fails, leave as string
                pass
    return deserialized_dict


class FileExporter(SpanExporter):
    """An OpenTelemetry span exporter that writes spans to a JSONLines file.

    The exported file contains one JSON object per line, each representing a UiPathEvalSpan.
    The file can be read with:
    - exporter.read_all_spans() method
    - Standard line-by-line JSON parsing for streaming
    """

    def __init__(self, file_path: str, **kwargs) -> None:
        """Initialize the exporter with the file path to write spans to.

        Args:
            file_path: Path to the file where spans will be written.
            **kwargs: Additional keyword arguments passed to the parent class.
        """
        super().__init__(**kwargs)
        self.file_path = Path(file_path)

        # Ensure the directory exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"FileSpanExporter initialized with file path: {self.file_path}")

    def _serialize_span_dict(self, span_dict: dict[str, Any]) -> dict[str, Any]:
        """Serialize datetime objects in the span dictionary to ISO format strings.

        Args:
            span_dict: Dictionary representation of a UiPathEvalSpan.

        Returns:
            Dictionary with datetime objects converted to ISO format strings.
        """
        serialized_dict = span_dict.copy()
        for key, value in serialized_dict.items():
            if isinstance(value, datetime):
                serialized_dict[key] = value.isoformat()
        return serialized_dict

    def _uipath_span_to_uipath_eval_span(
        self, uipath_span: UiPathSpan
    ) -> UiPathEvalSpan:
        """Convert a UiPathSpan to a UiPathEvalSpan."""
        # Parse attributes JSON to extract required data
        try:
            attributes_dict = (
                json.loads(uipath_span.attributes) if uipath_span.attributes else {}
            )
        except json.JSONDecodeError:
            attributes_dict = {}

        input_data = attributes_dict.get("inputs", {})
        if isinstance(input_data, str):
            try:
                input_data = json.loads(input_data)
            except json.JSONDecodeError:
                input_data = {"raw_input": input_data}
        elif not isinstance(input_data, dict):
            input_data = {"input": input_data}

        output_data = attributes_dict.get("outputs", None)
        if output_data is not None and not isinstance(output_data, str):
            output_data = str(output_data)

        model = attributes_dict.get("model", None)

        status = Status.SUCCESS if uipath_span.status == 1 else Status.FAILURE

        start_time = datetime.fromisoformat(
            uipath_span.start_time.replace("Z", "+00:00")
        )
        end_time = datetime.fromisoformat(uipath_span.end_time.replace("Z", "+00:00"))

        return UiPathEvalSpan(
            input=input_data,
            output=output_data,
            model=model,
            start_time=start_time,
            end_time=end_time,
            name=uipath_span.name,
            parent_id=str(uipath_span.parent_id) if uipath_span.parent_id else "",
            id=str(uipath_span.id),
            status=status,
        )

    def _otel_span_to_uipath_eval_span(self, otel_span: ReadableSpan) -> UiPathEvalSpan:
        """Convert an OpenTelemetry span to a UiPathEvalSpan."""
        uipath_span = _SpanUtils.otel_span_to_uipath_span(otel_span)
        return self._uipath_span_to_uipath_eval_span(uipath_span)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export spans to the configured file.

        Efficiently appends spans as JSON lines to the file.

        Args:
            spans: Sequence of ReadableSpan objects to export.

        Returns:
            SpanExportResult indicating success or failure.
        """
        try:
            logger.debug(f"Exporting {len(spans)} spans to file: {self.file_path}")

            # Convert OpenTelemetry spans to UiPathEvalSpan objects
            new_eval_spans = [
                self._otel_span_to_uipath_eval_span(span) for span in spans
            ]

            # Append each span as a JSON line
            with open(self.file_path, "a", encoding="utf-8") as f:
                for span in new_eval_spans:
                    # Convert the span to a dictionary for JSON serialization
                    span_dict = (
                        span.model_dump()
                        if hasattr(span, "model_dump")
                        else span.__dict__
                    )
                    # Handle datetime serialization
                    span_dict = self._serialize_span_dict(span_dict)
                    json_line = json.dumps(span_dict, separators=(",", ":"))
                    f.write(json_line + "\n")

            logger.debug(
                f"Successfully exported {len(spans)} spans to {self.file_path}"
            )
            return SpanExportResult.SUCCESS

        except Exception as e:
            logger.error(f"Failed to export spans to file {self.file_path}: {e}")
            return SpanExportResult.FAILURE

    @staticmethod
    def read_all_spans(file_path: str | Path) -> List[UiPathEvalSpan]:
        """Read all spans from the file.

        Returns:
            List of all UiPathEvalSpan objects in the file.
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        if not file_path.exists() or file_path.stat().st_size == 0:
            return []

        spans = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        span_dict = json.loads(line)
                        # Deserialize datetime fields
                        span_dict = _deserialize_span_dict(span_dict)
                        # Create UiPathEvalSpan from the dictionary
                        span = UiPathEvalSpan(**span_dict)
                        spans.append(span)
                    except json.JSONDecodeError as e:
                        logger.warning(
                            f"Failed to parse JSON on line {line_num} in {file_path}: {e}"
                        )
                        continue
                    except Exception as e:
                        logger.warning(
                            f"Failed to create UiPathEvalSpan from line {line_num} in {file_path}: {e}"
                        )
                        continue

            return spans
        except Exception as e:
            logger.error(f"Unexpected error reading spans from file {file_path}: {e}")
            return []

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush the exporter.

        Args:
            timeout_millis: Timeout in milliseconds (not used for file operations).

        Returns:
            True if flush was successful, False otherwise.
        """
        logger.debug("FileSpanExporter force_flush completed")
        return True
