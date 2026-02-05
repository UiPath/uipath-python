import inspect
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from os import environ as env
from typing import Any, Dict, List, Optional

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import StatusCode
from pydantic import BaseModel, ConfigDict, Field
from uipath.core.serialization import serialize_json

logger = logging.getLogger(__name__)

# SourceEnum.Robots = 4 (default for Python SDK / coded agents)
DEFAULT_SOURCE = 4


class AttachmentProvider(IntEnum):
    ORCHESTRATOR = 0


class AttachmentDirection(IntEnum):
    NONE = 0
    IN = 1
    OUT = 2


class SpanAttachment(BaseModel):
    """Represents an attachment in the UiPath tracing system."""

    model_config = ConfigDict(populate_by_name=True, use_enum_values=True)

    id: str = Field(..., alias="id")
    file_name: str = Field(..., alias="fileName")
    mime_type: str = Field(..., alias="mimeType")
    provider: AttachmentProvider = Field(
        default=AttachmentProvider.ORCHESTRATOR, alias="provider"
    )
    direction: AttachmentDirection = Field(
        default=AttachmentDirection.NONE, alias="direction"
    )


@dataclass
class UiPathSpan:
    """Represents a span in the UiPath tracing system.

    Note: attributes can be either a JSON string (backwards compatible) or a dict (optimized).
    IDs are stored as OTEL hex strings (32 chars for trace_id, 16 chars for span_id/parent_id).
    """

    id: str  # 16-char hex (OTEL span ID format)
    trace_id: str  # 32-char hex (OTEL trace ID format)
    name: str
    attributes: str | Dict[str, Any]  # Support both str (legacy) and dict (optimized)
    parent_id: Optional[str] = None  # 16-char hex (OTEL span ID format)
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
    source: int = DEFAULT_SOURCE
    span_type: str = "Coded Agents"
    process_key: Optional[str] = field(
        default_factory=lambda: env.get("UIPATH_PROCESS_UUID")
    )
    reference_id: Optional[str] = field(
        default_factory=lambda: env.get("TRACE_REFERENCE_ID")
    )

    job_key: Optional[str] = field(default_factory=lambda: env.get("UIPATH_JOB_KEY"))

    # Top-level fields for internal tracing schema
    execution_type: Optional[int] = None
    agent_version: Optional[str] = None
    attachments: Optional[List[SpanAttachment]] = None

    def to_dict(self, serialize_attributes: bool = True) -> Dict[str, Any]:
        """Convert the Span to a dictionary suitable for JSON serialization.

        Args:
            serialize_attributes: If True and attributes is a dict, serialize to JSON string.
                                 If False, keep attributes as-is (dict or str).
                                 Default True for backwards compatibility.
        """
        attributes_out = self.attributes
        if serialize_attributes and isinstance(self.attributes, dict):
            attributes_out = json.dumps(self.attributes)

        attachments_out = None
        if self.attachments is not None:
            attachments_out = [
                {
                    "Id": att.id,
                    "FileName": att.file_name,
                    "MimeType": att.mime_type,
                    "Provider": int(att.provider),
                    "Direction": int(att.direction),
                }
                for att in self.attachments
            ]

        return {
            "Id": self.id,
            "TraceId": self.trace_id,
            "ParentId": self.parent_id,
            "Name": self.name,
            "StartTime": self.start_time,
            "EndTime": self.end_time,
            "Attributes": attributes_out,
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
            "ExecutionType": self.execution_type,
            "AgentVersion": self.agent_version,
            "Attachments": attachments_out,
        }


class _SpanUtils:
    @staticmethod
    def normalize_trace_id(value: str) -> str:
        """Normalize trace ID to 32-char OTEL hex format.

        Accepts both UUID format (with dashes) and OTEL hex format (32 chars).
        Returns lowercase 32-char hex string.
        """
        # Remove dashes if UUID format
        normalized = value.replace("-", "").lower()
        if len(normalized) != 32:
            raise ValueError(f"Invalid trace ID format: {value}")
        return normalized

    @staticmethod
    def normalize_span_id(value: str) -> str:
        """Normalize span ID to 16-char OTEL hex format.

        Accepts both UUID format (with dashes, uses last 16 hex chars) and OTEL hex format (16 chars).
        Returns lowercase 16-char hex string.
        """
        # Remove dashes if UUID format
        normalized = value.replace("-", "").lower()
        if len(normalized) == 32:
            # UUID format - take last 16 chars (span ID portion)
            return normalized[16:]
        elif len(normalized) == 16:
            return normalized
        else:
            raise ValueError(f"Invalid span ID format: {value}")

    @staticmethod
    def otel_span_to_uipath_span(
        otel_span: ReadableSpan,
        custom_trace_id: Optional[str] = None,
        serialize_attributes: bool = True,
    ) -> UiPathSpan:
        """Convert an OpenTelemetry span to a UiPathSpan.

        Args:
            otel_span: The OpenTelemetry span to convert
            custom_trace_id: Optional custom trace ID to use (UUID or OTEL hex format)
            serialize_attributes: If True, serialize attributes to JSON string (backwards compatible).
                                 If False, keep as dict for optimized processing. Default True.
        """
        # Extract the context information from the OTel span
        span_context = otel_span.get_span_context()

        # Convert to OTEL hex format (32 chars for trace_id, 16 chars for span_id)
        trace_id = format(span_context.trace_id, "032x")
        span_id = format(span_context.span_id, "016x")

        # Override trace_id if custom or env var provided (supports both UUID and hex format)
        trace_id_override = custom_trace_id or os.environ.get("UIPATH_TRACE_ID")
        if trace_id_override:
            trace_id = _SpanUtils.normalize_trace_id(trace_id_override)

        # Get parent span ID if it exists
        parent_id: Optional[str] = None
        if otel_span.parent is not None:
            parent_id = format(otel_span.parent.span_id, "016x")
        else:
            # Only set UIPATH_PARENT_SPAN_ID for root spans (spans without a parent)
            parent_span_id_str = env.get("UIPATH_PARENT_SPAN_ID")
            if parent_span_id_str:
                parent_id = _SpanUtils.normalize_span_id(parent_span_id_str)

        # Build attributes dict efficiently
        # Use the otel attributes as base - we only add new keys, don't modify existing
        otel_attrs = otel_span.attributes if otel_span.attributes else {}
        # Only copy if we need to modify - we'll build attributes_dict lazily
        attributes_dict: dict[str, Any] = dict(otel_attrs) if otel_attrs else {}

        # Map status
        status = 1  # Default to OK
        if otel_span.status.status_code == StatusCode.ERROR:
            status = 2  # Error
            attributes_dict["error"] = otel_span.status.description

        # Process inputs - avoid redundant parsing if already parsed
        original_inputs = otel_attrs.get("input", None)
        if original_inputs:
            if isinstance(original_inputs, str):
                try:
                    attributes_dict["input.value"] = json.loads(original_inputs)
                    attributes_dict["input.mime_type"] = "application/json"
                except Exception:
                    attributes_dict["input.value"] = original_inputs
            else:
                attributes_dict["input.value"] = original_inputs

        # Process outputs - avoid redundant parsing if already parsed
        original_outputs = otel_attrs.get("output", None)
        if original_outputs:
            if isinstance(original_outputs, str):
                try:
                    attributes_dict["output.value"] = json.loads(original_outputs)
                    attributes_dict["output.mime_type"] = "application/json"
                except Exception:
                    attributes_dict["output.value"] = original_outputs
            else:
                attributes_dict["output.value"] = original_outputs

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

        # Top-level fields for internal tracing schema
        execution_type = attributes_dict.get("executionType")
        agent_version = attributes_dict.get("agentVersion")
        reference_id = attributes_dict.get("referenceId")

        # Source: override via uipath.source attribute, else DEFAULT_SOURCE
        uipath_source = attributes_dict.get("uipath.source")
        source = uipath_source if isinstance(uipath_source, int) else DEFAULT_SOURCE

        attachments = None
        attachments_data = attributes_dict.get("attachments")
        if attachments_data:
            try:
                attachments_list = json.loads(attachments_data)
                attachments = [
                    SpanAttachment(
                        id=att.get("id"),
                        file_name=att.get("fileName", ""),
                        mime_type=att.get("mimeType", ""),
                        provider=att.get("provider", 0),
                        direction=att.get("direction", 0),
                    )
                    for att in attachments_list
                ]
            except Exception as e:
                logger.warning(f"Error processing attachments: {e}")

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
            attributes=json.dumps(attributes_dict)
            if serialize_attributes
            else attributes_dict,
            start_time=start_time,
            end_time=end_time_str,
            status=status,
            span_type=span_type,
            execution_type=execution_type,
            agent_version=agent_version,
            reference_id=reference_id,
            source=source,
            attachments=attachments,
        )

    @staticmethod
    def format_object_for_trace_json(
        input_object: Any,
    ) -> str:
        """Return a JSON string of inputs from the function signature."""
        return serialize_json(input_object)

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

    @staticmethod
    def spans_to_llm_context(spans: list[ReadableSpan]) -> str:
        """Convert spans to a formatted conversation history string suitable for LLM context.

        Includes function calls (including LLM calls) with their inputs and outputs.
        """
        history = []
        for span in spans:
            attributes = dict(span.attributes) if span.attributes else {}

            input_value = attributes.get("input.value")
            output_value = attributes.get("output.value")
            telemetry_filter = attributes.get("telemetry.filter")

            if not input_value or not output_value or telemetry_filter == "drop":
                continue

            history.append(f"Function: {span.name}")
            history.append(f"Input: {input_value}")
            history.append(f"Output: {output_value}")
            history.append("")

        if not history:
            return "(empty)"

        return "\n".join(history)
