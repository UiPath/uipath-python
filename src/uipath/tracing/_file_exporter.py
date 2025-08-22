import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import List, Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)

from uipath.tracing._models import Status, UiPathEvalSpan

from ._utils import UiPathSpan, _SpanUtils

logger = logging.getLogger(__name__)


class FileExporter(SpanExporter):
    """An OpenTelemetry span exporter that writes spans to a pickle file.

    The exported file contains a single list of UiPathEvalSpan objects that can be read with:
    - exporter.read_all_spans() method
    - Standard pickle.load(file) to get the complete list
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

    def _uipath_span_to_uipath_eval_span(
        self, uipath_span: UiPathSpan
    ) -> UiPathEvalSpan:
        """Convert a UiPathSpan to a UiPathEvalSpan."""
        # Parse attributes JSON to extract input, output, and model
        try:
            attributes_dict = (
                json.loads(uipath_span.attributes) if uipath_span.attributes else {}
            )
        except json.JSONDecodeError:
            attributes_dict = {}

        # Extract input and output from attributes
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

        # Extract model information
        model = attributes_dict.get("model", None)

        # Map status from int to Status enum
        status = Status.SUCCESS if uipath_span.status == 1 else Status.FAILURE

        # Convert ISO string timestamps to datetime objects
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

        Efficiently appends spans while maintaining a single readable list format.

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

            # TODO: find a more efficient way of writing the spans
            if self.file_path.exists() and self.file_path.stat().st_size > 0:
                try:
                    with open(self.file_path, "rb") as f:
                        existing_spans = pickle.load(f)
                except (pickle.PickleError, EOFError):
                    existing_spans = []
            else:
                existing_spans = []

            all_spans = existing_spans + new_eval_spans

            with open(self.file_path, "wb") as f:
                pickle.dump(all_spans, f)

            logger.debug(
                f"Successfully exported {len(spans)} spans to {self.file_path}. Total spans: {len(all_spans)}"
            )
            return SpanExportResult.SUCCESS

        except Exception as e:
            logger.error(f"Failed to export spans to file {self.file_path}: {e}")
            return SpanExportResult.FAILURE

    def read_all_spans(self) -> List[UiPathEvalSpan]:
        """Read all spans from the file.

        Returns:
            List of all UiPathEvalSpan objects in the file.
        """
        if not self.file_path.exists() or self.file_path.stat().st_size == 0:
            return []

        try:
            with open(self.file_path, "rb") as f:
                spans = pickle.load(f)
                return spans if isinstance(spans, list) else []
        except (pickle.PickleError, EOFError) as e:
            logger.error(f"Failed to read spans from file {self.file_path}: {e}")
            return []
        except Exception as e:
            logger.error(
                f"Unexpected error reading spans from file {self.file_path}: {e}"
            )
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
