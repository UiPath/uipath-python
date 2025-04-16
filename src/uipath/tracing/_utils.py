import inspect
import json
import logging
import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from os import environ as env
from typing import Any, Dict, Optional

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import StatusCode

logger = logging.getLogger(__name__)


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
        default_factory=lambda: env.get("UIPATH_FOLDER_KEY_XYZ", "")
    )
    source: Optional[str] = None
    span_type: str = "Coded Agents"
    process_key: Optional[str] = field(
        default_factory=lambda: env.get("UIPATH_PROCESS_UUID")
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
    def otel_span_to_uipath_span(otel_span: ReadableSpan) -> UiPathSpan:
        """Convert an OpenTelemetry span to a UiPathSpan."""
        # Extract the context information from the OTel span
        span_context = otel_span.get_span_context()

        # OTel uses hexadecimal strings, we need to convert to UUID
        trace_id = _SpanUtils.trace_id_to_uuid4(span_context.trace_id)
        span_id = _SpanUtils.span_id_to_uuid4(span_context.span_id)

        trace_id_str = os.environ.get("UIPATH_TRACE_ID")
        if trace_id_str:
            trace_id = uuid.UUID(trace_id_str)

        # Get parent span ID if it exists
        parent_id = None
        if otel_span.parent is not None:
            parent_id = _SpanUtils.span_id_to_uuid4(otel_span.parent.span_id)

        # Map status
        status = 1  # Default to OK
        if otel_span.status.status_code == StatusCode.ERROR:
            status = 2  # Error

        # Convert attributes to a format compatible with UiPathSpan
        attributes_dict: dict[str, Any] = (
            dict(otel_span.attributes) if otel_span.attributes else {}
        )

        original_inputs = attributes_dict.get("inputs", None)
        original_outputs = attributes_dict.get("outputs", None)

        if original_inputs:
            try:
                if isinstance(original_inputs, str):
                    json_inputs = json.loads(original_inputs)
                    attributes_dict["inputs"] = json_inputs
                else:
                    attributes_dict["inputs"] = original_inputs
            except Exception as e:
                print(f"Error parsing inputs: {e}")
                attributes_dict["inputs"] = str(original_inputs)

        if original_outputs:
            try:
                if isinstance(original_outputs, str):
                    json_outputs = json.loads(original_outputs)
                    attributes_dict["outputs"] = json_outputs
                else:
                    attributes_dict["outputs"] = original_outputs
            except Exception as e:
                print(f"Error parsing outputs: {e}")
                attributes_dict["outputs"] = str(original_outputs)

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
        return json.dumps(result, default=str)

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
