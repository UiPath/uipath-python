import json
from asyncio import sleep
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Sequence

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

from uipath.tracing._traced import traced


class InMemorySpanExporter(SpanExporter):
    """An OpenTelemetry span exporter that stores spans in memory for testing."""

    def __init__(self):
        self.spans = []
        self.is_shutdown = False

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        if self.is_shutdown:
            return SpanExportResult.FAILURE

        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def get_exported_spans(self) -> List[ReadableSpan]:
        return self.spans

    def clear_exported_spans(self) -> None:
        self.spans = []

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return not self.is_shutdown

    def shutdown(self) -> None:
        self.is_shutdown = True


@pytest.fixture
def setup_tracer():
    # Setup InMemorySpanExporter and TracerProvider
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(exporter))  # type: ignore

    yield exporter, provider


def test_traced_sync_function(setup_tracer):
    exporter, provider = setup_tracer

    @traced()
    def sample_function(x, y):
        return x + y

    result = sample_function(2, 3)
    assert result == 5

    provider.shutdown()  # Ensure spans are flushed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]
    assert span.name == "sample_function"
    assert span.attributes["span_type"] == "function_call_sync"
    assert "inputs" in span.attributes
    assert "output" in span.attributes
    assert span.attributes["output"] == "5"


@pytest.mark.asyncio
async def test_traced_async_function(setup_tracer):
    exporter, provider = setup_tracer

    @traced()
    async def sample_async_function(x, y):
        return x * y

    result = await sample_async_function(2, 3)
    assert result == 6

    provider.shutdown()  # Ensure spans are flushed

    await sleep(1)
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]
    assert span.name == "sample_async_function"
    assert span.attributes["span_type"] == "function_call_async"
    assert "inputs" in span.attributes
    assert "output" in span.attributes
    assert span.attributes["output"] == "6"


def test_traced_generator_function(setup_tracer):
    exporter, provider = setup_tracer

    @traced()
    def sample_generator_function(n):
        for i in range(n):
            yield i

    results = list(sample_generator_function(3))
    assert results == [0, 1, 2]

    provider.shutdown()  # Ensure spans are flushed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]
    assert span.name == "sample_generator_function"
    assert span.attributes["span_type"] == "function_call_generator_sync"
    assert "inputs" in span.attributes
    assert "output" in span.attributes
    assert span.attributes["output"] == "[0, 1, 2]"


@pytest.mark.asyncio
async def test_traced_async_generator_function(setup_tracer):
    exporter, provider = setup_tracer

    @traced()
    async def sample_async_generator_function(n):
        for i in range(n):
            yield i

    results = [item async for item in sample_async_generator_function(3)]
    assert results == [0, 1, 2]

    provider.shutdown()  # Ensure spans are flushed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]
    assert span.name == "sample_async_generator_function"
    assert span.attributes["span_type"] == "function_call_generator_async"
    assert "inputs" in span.attributes
    assert "output" in span.attributes
    assert span.attributes["output"] == "[0, 1, 2]"


def test_traced_with_basic_processors(setup_tracer):
    """Test traced decorator with basic input and output processors."""
    exporter, provider = setup_tracer

    def double_input(inputs):
        """Double numeric inputs."""
        result = inputs.copy()
        for key, value in result.items():
            if isinstance(value, (int, float)):
                result[key] = value * 2
        return result

    def format_output(output):
        """Format the output as a string."""
        return {"result": str(output)}

    @traced(input_processor=double_input, output_processor=format_output)
    def multiply(x, y):
        return x * y

    # Original function behavior should be unchanged
    result = multiply(3, 4)
    assert result == 12

    provider.shutdown()  # Ensure spans are flushed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]

    # Check that input processor was applied (doubles the inputs)
    inputs_json = span.attributes["inputs"]
    inputs = json.loads(inputs_json)
    assert inputs["x"] == 6  # 3 doubled to 6
    assert inputs["y"] == 8  # 4 doubled to 8

    # Check that output processor was applied (formatted as string in dict)
    output_json = span.attributes["output"]
    output = json.loads(output_json)
    assert output == {"result": "12"}  # Result wrapped in dict with string conversion


@pytest.mark.asyncio
async def test_traced_async_with_basic_processors(setup_tracer):
    """Test traced decorator with basic processors for async functions."""
    exporter, provider = setup_tracer

    def add_context(inputs):
        """Add context to inputs."""
        result = inputs.copy()
        result["context"] = "test"
        return result

    def add_timestamp(output):
        """Add a timestamp to output."""
        if isinstance(output, dict):
            result = output.copy()
            result["processed"] = True
            return result
        return {"value": output, "processed": True}

    @traced(input_processor=add_context, output_processor=add_timestamp)
    async def async_operation(message):
        await sleep(0.1)
        return {"status": "completed", "message": message}

    # Original function behavior should be unchanged
    result = await async_operation("hello")
    assert result == {"status": "completed", "message": "hello"}

    provider.shutdown()  # Ensure spans are flushed
    await sleep(0.1)  # Give time for spans to be processed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]

    # Check that input processor was applied
    inputs_json = span.attributes["inputs"]
    inputs = json.loads(inputs_json)
    assert inputs["message"] == "hello"
    assert inputs["context"] == "test"  # Added by processor

    # Check that output processor was applied
    output_json = span.attributes["output"]
    output = json.loads(output_json)
    assert output["status"] == "completed"
    assert output["message"] == "hello"
    assert output["processed"] is True  # Added by processor


def mask_credit_card(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Process inputs to mask credit card information."""
    processed = inputs.copy()
    if "card_number" in processed:
        if len(processed["card_number"]) >= 4:
            # Keep only the last 4 digits
            processed["card_number"] = "**** **** **** " + processed["card_number"][-4:]
        else:
            processed["card_number"] = "****"
    return processed


def anonymize_single_user_data(output_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single dictionary to anonymize user information."""
    processed = output_dict.copy()
    if "user_info" in processed and isinstance(processed["user_info"], dict):
        user_info = processed["user_info"].copy()
        if "name" in user_info:
            user_info["name"] = "Anonymous User"
        if "email" in user_info:
            user_info["email"] = "anonymous@example.com"
        processed["user_info"] = user_info
    return processed


def anonymize_user_data(output: Any) -> Any:
    """Process outputs to anonymize user information."""
    # Handle list of outputs (from generators)
    if isinstance(output, list):
        processed_outputs = []
        for item in output:
            if isinstance(item, dict):
                processed_outputs.append(anonymize_single_user_data(item))
            else:
                processed_outputs.append(item)
        return processed_outputs

    # Handle single dictionary output
    if not isinstance(output, dict):
        return output

    return anonymize_single_user_data(output)


def dataclass_to_dict(obj):
    """Convert a dataclass instance or list of dataclass instances to dict(s)."""
    if isinstance(obj, list):
        return [dataclass_to_dict(item) for item in obj]

    # Check if object is a dataclass (has __dataclass_fields__ attribute)
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)

    return obj


# Example of a processor that handles dataclasses
def process_dataclass_output(output):
    """Process output that might be a dataclass or contain dataclasses."""
    # First convert to dict if it's a dataclass
    data = dataclass_to_dict(output)

    # Now apply regular dict processing
    if isinstance(data, dict):
        # Apply your masking/anonymization logic
        if "sensitive_field" in data:
            data["sensitive_field"] = "***MASKED***"

        # Check for direct email field (for UserProfile dataclass)
        if "email" in data:
            data["email"] = "anonymous@example.com"

        # Process nested user_info if present
        if "user_info" in data and isinstance(data["user_info"], dict):
            if "email" in data["user_info"]:
                data["user_info"]["email"] = "anonymous@example.com"

    return data


# Example of using with a dataclass
@dataclass
class UserProfile:
    user_id: int
    name: str
    email: str
    access_level: str


def test_traced_with_input_processor(setup_tracer):
    exporter, provider = setup_tracer

    @traced(input_processor=mask_credit_card)
    def process_payment(name, card_number, amount):
        return {"transaction_id": "tx_12345", "amount": amount, "status": "approved"}

    result = process_payment("John Doe", "4111111111111111", 99.99)
    assert result["transaction_id"] == "tx_12345"

    provider.shutdown()  # Ensure spans are flushed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]
    assert span.name == "process_payment"

    # Verify inputs were processed
    inputs_json = span.attributes["inputs"]
    inputs = json.loads(inputs_json)
    assert "card_number" in inputs
    assert inputs["card_number"] == "**** **** **** 1111"  # Should be masked
    assert inputs["name"] == "John Doe"  # Should be unchanged

    # Verify original function output is returned
    assert result["transaction_id"] == "tx_12345"
    assert result["amount"] == 99.99


def test_traced_with_output_processor(setup_tracer):
    exporter, provider = setup_tracer

    @traced(output_processor=anonymize_user_data)
    def get_user_profile(user_id):
        # Return sensitive user data
        return {
            "user_id": user_id,
            "user_info": {"name": "Jane Smith", "email": "jane@example.com", "age": 32},
            "subscription": "premium",
        }

    result = get_user_profile(12345)

    # Original function should return unmodified data
    assert result["user_info"]["name"] == "Jane Smith"
    assert result["user_info"]["email"] == "jane@example.com"

    provider.shutdown()  # Ensure spans are flushed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]

    # Verify output was processed for tracing
    output_json = span.attributes["output"]
    output = json.loads(output_json)
    assert output["user_info"]["name"] == "Anonymous User"
    assert output["user_info"]["email"] == "anonymous@example.com"
    assert output["user_info"]["age"] == 32  # Non-sensitive data preserved
    assert output["subscription"] == "premium"  # Non-sensitive data preserved


def test_traced_with_dataclass_output(setup_tracer):
    exporter, provider = setup_tracer

    @traced(output_processor=process_dataclass_output)
    def get_user_profile(user_id):
        # Return a dataclass with sensitive data
        return UserProfile(
            user_id=user_id,
            name="John Doe",
            email="john.doe@example.com",
            access_level="admin",
        )

    result = get_user_profile(12345)

    # Verify original result is unchanged
    assert result.name == "John Doe"
    assert result.email == "john.doe@example.com"

    provider.shutdown()
    spans = exporter.get_exported_spans()

    # Verify the output was processed for tracing
    output_json = spans[0].attributes["output"]
    output = json.loads(output_json)
    assert "email" in output
    assert output["email"] == "anonymous@example.com"  # Masked in the trace


@pytest.mark.asyncio
async def test_traced_async_with_processors(setup_tracer):
    exporter, provider = setup_tracer

    @traced(input_processor=mask_credit_card, output_processor=anonymize_user_data)
    async def async_payment_with_user_data(name, card_number, amount):
        await sleep(0.1)  # Simulate async operation
        return {
            "transaction_id": "tx_async_12345",
            "amount": amount,
            "status": "approved",
            "user_info": {
                "name": name,
                "email": f"{name.lower().replace(' ', '.')}@example.com",
            },
        }

    result = await async_payment_with_user_data("John Doe", "5555555555554444", 199.99)

    # Original function should return unmodified data
    assert result["transaction_id"] == "tx_async_12345"
    assert result["user_info"]["name"] == "John Doe"
    assert result["user_info"]["email"] == "john.doe@example.com"

    provider.shutdown()  # Ensure spans are flushed
    await sleep(0.1)  # Give time for spans to be processed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]

    # Verify inputs were processed
    inputs_json = span.attributes["inputs"]
    inputs = json.loads(inputs_json)
    assert inputs["card_number"] == "**** **** **** 4444"

    # Verify outputs were processed
    output_json = span.attributes["output"]
    output = json.loads(output_json)
    assert output["user_info"]["name"] == "Anonymous User"
    assert output["user_info"]["email"] == "anonymous@example.com"
    assert output["amount"] == 199.99  # Non-sensitive data preserved


def test_traced_generator_with_processors(setup_tracer):
    exporter, provider = setup_tracer

    @traced(input_processor=mask_credit_card, output_processor=anonymize_user_data)
    def generate_user_transactions(card_number, count):
        for i in range(count):
            yield {
                "transaction_id": f"tx_{i}",
                "amount": 10.0 * (i + 1),
                "user_info": {"name": "Jane Smith", "email": "jane@example.com"},
            }

    results = list(generate_user_transactions("4111111111111111", 3))

    # Original function should return unmodified data
    assert len(results) == 3
    assert results[0]["user_info"]["name"] == "Jane Smith"
    assert results[0]["user_info"]["email"] == "jane@example.com"

    provider.shutdown()  # Ensure spans are flushed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]

    # Verify inputs were processed
    inputs_json = span.attributes["inputs"]
    inputs = json.loads(inputs_json)
    assert inputs["card_number"] == "**** **** **** 1111"

    # Verify outputs were processed
    output_json = span.attributes["output"]
    output = json.loads(output_json)
    assert len(output) == 3
    for transaction in output:
        assert transaction["user_info"]["name"] == "Anonymous User"
        assert transaction["user_info"]["email"] == "anonymous@example.com"


@pytest.mark.asyncio
async def test_traced_async_generator_with_processors(setup_tracer):
    exporter, provider = setup_tracer

    @traced(input_processor=mask_credit_card, output_processor=anonymize_user_data)
    async def generate_async_transactions(card_number, count):
        for i in range(count):
            await sleep(0.05)  # Simulate async operation
            yield {
                "transaction_id": f"tx_async_{i}",
                "amount": 20.0 * (i + 1),
                "user_info": {"name": "Bob Johnson", "email": "bob@example.com"},
            }

    results = [
        item async for item in generate_async_transactions("5555555555554444", 2)
    ]

    # Original function should return unmodified data
    assert len(results) == 2
    assert results[0]["user_info"]["name"] == "Bob Johnson"
    assert results[0]["user_info"]["email"] == "bob@example.com"

    provider.shutdown()  # Ensure spans are flushed
    await sleep(0.1)  # Give time for spans to be processed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]

    # Verify inputs were processed
    inputs_json = span.attributes["inputs"]
    inputs = json.loads(inputs_json)
    assert inputs["card_number"] == "**** **** **** 4444"

    # Verify outputs were processed
    output_json = span.attributes["output"]
    output = json.loads(output_json)
    assert len(output) == 2
    for transaction in output:
        assert transaction["user_info"]["name"] == "Anonymous User"
        assert transaction["user_info"]["email"] == "anonymous@example.com"


def test_traced_with_hide_input_outputs(setup_tracer):
    """Test that hide_input=True and hide_output=True redacts all data."""
    exporter, provider = setup_tracer

    @traced(hide_input=True, hide_output=True)
    def fully_private_function(sensitive_input):
        return {"sensitive_output": f"Processed {sensitive_input}"}

    result = fully_private_function("confidential_data")

    # Original function should return unmodified data
    assert result["sensitive_output"] == "Processed confidential_data"

    provider.shutdown()  # Ensure spans are flushed
    spans = exporter.get_exported_spans()

    assert len(spans) == 1
    span = spans[0]

    # Verify both inputs and outputs were redacted
    inputs_json = span.attributes["inputs"]
    inputs = json.loads(inputs_json)
    assert inputs == {"redacted": "Input data not logged for privacy/security"}

    output_json = span.attributes["output"]
    output = json.loads(output_json)
    assert output == {"redacted": "Output data not logged for privacy/security"}
