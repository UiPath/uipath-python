import inspect
import json
import logging
import os
import random
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from os import environ as env
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import StatusCode

logger = logging.getLogger(__name__)


def _simple_serialize_defaults(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True, mode="json")
    if hasattr(obj, "dict"):
        return obj.dict()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()

    # Handle dataclasses
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)

    # Handle enums
    if isinstance(obj, Enum):
        return obj.value

    if isinstance(obj, (set, tuple)):
        if hasattr(obj, "_asdict") and callable(obj._asdict):
            return obj._asdict()
        return list(obj)

    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, (timezone, ZoneInfo)):
        return obj.tzname(None)

    return str(obj)


@dataclass
class UiPathSpan:
    """Represents a span in the UiPath tracing system."""

    id: uuid.UUID
    trace_id: uuid.UUID
    name: str
    attributes: str
    parent_id: Optional[uuid.UUID] = None
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: str = field(default_factory=lambda: datetime.now().isoformat())
    status: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat() + "Z")
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat() + "Z")
    organization_id: Optional[str] = field(
        default_factory=lambda: env.get("UIPATH_ORGANIZATION_ID", "")
    )
    tenant_id: Optional[str] = field(
        default_factory=lambda: env.get("UIPATH_TENANT_ID", "")
    )
    expiry_time_utc: Optional[str] = None
    folder_key: Optional[str] = field(
        default_factory=lambda: env.get("UIPATH_FOLDER_KEY", "")
    )
    source: Optional[str] = None
    span_type: str = "Coded Agents"
    process_key: Optional[str] = field(
        default_factory=lambda: env.get("UIPATH_PROCESS_UUID")
    )
    reference_id: Optional[str] = field(
        default_factory=lambda: env.get("TRACE_REFERENCE_ID")
    )

    job_key: Optional[str] = field(default_factory=lambda: env.get("UIPATH_JOB_KEY"))

    def to_dict(self) -> Dict[str, Any]:
        """Convert the Span to a dictionary suitable for JSON serialization."""
        return {
            "Id": str(self.id),
            "TraceId": str(self.trace_id),
            "ParentId": str(self.parent_id) if self.parent_id else None,
            "Name": self.name,
            "StartTime": self.start_time,
            "EndTime": self.end_time,
            "Attributes": self.attributes,
            "Status": self.status,
            "CreatedAt": self.created_at,
            "UpdatedAt": self.updated_at,
            "OrganizationId": self.organization_id,
            "TenantId": self.tenant_id,
            "ExpiryTimeUtc": self.expiry_time_utc,
            "FolderKey": self.folder_key,
            "Source": self.source,
            "SpanType": self.span_type,
            "ProcessKey": self.process_key,
            "JobKey": self.job_key,
            "ReferenceId": self.reference_id,
        }


class _SpanUtils:
    @staticmethod
    def span_id_to_uuid4(span_id: int) -> uuid.UUID:
        """Convert a 64-bit span ID to a valid UUID4 format.

        Creates a UUID where:
        - The 64 least significant bits contain the span ID
        - The UUID version (bits 48-51) is set to 4
        - The UUID variant (bits 64-65) is set to binary 10
        """
        # Generate deterministic high bits using the span_id as seed
        temp_random = random.Random(span_id)
        high_bits = temp_random.getrandbits(64)

        # Combine high bits and span ID into a 128-bit integer
        combined = (high_bits << 64) | span_id

        # Set version to 4 (UUID4)
        combined = (combined & ~(0xF << 76)) | (0x4 << 76)

        # Set variant to binary 10
        combined = (combined & ~(0x3 << 62)) | (2 << 62)

        # Convert to hex string in UUID format
        hex_str = format(combined, "032x")
        return uuid.UUID(hex_str)

    @staticmethod
    def trace_id_to_uuid4(trace_id: int) -> uuid.UUID:
        """Convert a 128-bit trace ID to a valid UUID4 format.

        Modifies the trace ID to conform to UUID4 requirements:
        - The UUID version (bits 48-51) is set to 4
        - The UUID variant (bits 64-65) is set to binary 10
        """
        # Set version to 4 (UUID4)
        uuid_int = (trace_id & ~(0xF << 76)) | (0x4 << 76)

        # Set variant to binary 10
        uuid_int = (uuid_int & ~(0x3 << 62)) | (2 << 62)

        # Convert to hex string in UUID format
        hex_str = format(uuid_int, "032x")
        return uuid.UUID(hex_str)

    @staticmethod
    def otel_span_to_uipath_span(
        otel_span: ReadableSpan, custom_trace_id: Optional[str] = None
    ) -> UiPathSpan:
        """Convert an OpenTelemetry span to a UiPathSpan."""
        # Extract the context information from the OTel span
        span_context = otel_span.get_span_context()

        # OTel uses hexadecimal strings, we need to convert to UUID
        trace_id = _SpanUtils.trace_id_to_uuid4(span_context.trace_id)
        span_id = _SpanUtils.span_id_to_uuid4(span_context.span_id)

        trace_id_str = custom_trace_id or os.environ.get("UIPATH_TRACE_ID")
        if trace_id_str:
            trace_id = uuid.UUID(trace_id_str)

        # Get parent span ID if it exists
        parent_id = None
        if otel_span.parent is not None:
            parent_id = _SpanUtils.span_id_to_uuid4(otel_span.parent.span_id)

        parent_span_id_str = env.get("UIPATH_PARENT_SPAN_ID")

        if parent_span_id_str:
            parent_id = uuid.UUID(parent_span_id_str)

        # Convert attributes to a format compatible with UiPathSpan
        attributes_dict: dict[str, Any] = (
            dict(otel_span.attributes) if otel_span.attributes else {}
        )

        # Map status
        status = 1  # Default to OK
        if otel_span.status.status_code == StatusCode.ERROR:
            status = 2  # Error
            attributes_dict["error"] = otel_span.status.description

        original_inputs = attributes_dict.get("input", None)
        original_outputs = attributes_dict.get("output", None)

        if original_inputs:
            try:
                if isinstance(original_inputs, str):
                    json_inputs = json.loads(original_inputs)
                    attributes_dict["input.value"] = json_inputs
                    attributes_dict["input.mime_type"] = "application/json"
                else:
                    attributes_dict["input.value"] = original_inputs
            except Exception as e:
                logger.warning(f"Error parsing inputs: {e}")
                attributes_dict["input.value"] = str(original_inputs)

        if original_outputs:
            try:
                if isinstance(original_outputs, str):
                    json_outputs = json.loads(original_outputs)
                    attributes_dict["output.value"] = json_outputs
                    attributes_dict["output.mime_type"] = "application/json"
                else:
                    attributes_dict["output.value"] = original_outputs
            except Exception as e:
                logger.warning(f"Error parsing output: {e}")
                attributes_dict["output.value"] = str(original_outputs)

        # Add events as additional attributes if they exist
        if otel_span.events:
            events_list = [
                {
                    "name": event.name,
                    "timestamp": event.timestamp,
                    "attributes": dict(event.attributes) if event.attributes else {},
                }
                for event in otel_span.events
            ]
            attributes_dict["events"] = events_list

        # Add links as additional attributes if they exist
        if hasattr(otel_span, "links") and otel_span.links:
            links_list = [
                {
                    "trace_id": link.context.trace_id,
                    "span_id": link.context.span_id,
                    "attributes": dict(link.attributes) if link.attributes else {},
                }
                for link in otel_span.links
            ]
            attributes_dict["links"] = links_list

        span_type_value = attributes_dict.get("span_type", "OpenTelemetry")
        span_type = str(span_type_value)

        # Create UiPathSpan from OpenTelemetry span
        start_time = datetime.fromtimestamp(
            (otel_span.start_time or 0) / 1e9
        ).isoformat()

        end_time_str = None
        if otel_span.end_time is not None:
            end_time_str = datetime.fromtimestamp(
                (otel_span.end_time or 0) / 1e9
            ).isoformat()
        else:
            end_time_str = datetime.now().isoformat()

        return UiPathSpan(
            id=span_id,
            trace_id=trace_id,
            parent_id=parent_id,
            name=otel_span.name,
            attributes=json.dumps(attributes_dict),
            start_time=start_time,
            end_time=end_time_str,
            status=status,
            span_type=span_type,
        )

    @staticmethod
    def format_args_for_trace_json(
        signature: inspect.Signature, *args: Any, **kwargs: Any
    ) -> str:
        """Return a JSON string of inputs from the function signature."""
        result = _SpanUtils.format_args_for_trace(signature, *args, **kwargs)
        return json.dumps(result, default=_simple_serialize_defaults)

    @staticmethod
    def format_object_for_trace_json(
        input_object: Any,
    ) -> str:
        """Return a JSON string of inputs from the function signature."""
        return json.dumps(input_object, default=_simple_serialize_defaults)

    @staticmethod
    def format_args_for_trace(
        signature: inspect.Signature, *args: Any, **kwargs: Any
    ) -> Dict[str, Any]:
        try:
            """Return a dictionary of inputs from the function signature."""
            # Create a parameter mapping by partially binding the arguments

            parameter_binding = signature.bind_partial(*args, **kwargs)

            # Fill in default values for any unspecified parameters
            parameter_binding.apply_defaults()

            # Extract the input parameters, skipping special Python parameters
            result = {}
            for name, value in parameter_binding.arguments.items():
                # Skip class and instance references
                if name in ("self", "cls"):
                    continue

                # Handle **kwargs parameters specially
                param_info = signature.parameters.get(name)
                if param_info and param_info.kind == inspect.Parameter.VAR_KEYWORD:
                    # Flatten nested kwargs directly into the result
                    if isinstance(value, dict):
                        result.update(value)
                else:
                    # Regular parameter
                    result[name] = value

            return result
        except Exception as e:
            logger.warning(
                f"Error formatting arguments for trace: {e}. Using args and kwargs directly."
            )
            return {"args": args, "kwargs": kwargs}
