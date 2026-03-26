import json

from tests.conftest import SpanCapture


def test_traced_with_pydantic_model_input(span_capture: SpanCapture):
    """Test tracing with Pydantic model as input."""
    from pydantic import BaseModel

    from uipath.core.tracing.decorators import traced

    class UserModel(BaseModel):
        name: str
        age: int

    @traced(name="process_user")
    def process_user(user: UserModel):
        return f"{user.name} is {user.age}"

    user = UserModel(name="Alice", age=30)
    result = process_user(user)

    assert result == "Alice is 30"

    spans = span_capture.get_spans()
    assert len(spans) == 1

    span = spans[0]
    # Verify input was serialized
    input_value = span.attributes.get("input.value")
    assert input_value is not None
    input_data = json.loads(input_value)
    assert input_data["user"]["name"] == "Alice"
    assert input_data["user"]["age"] == 30


def test_traced_with_dataclass_input(span_capture: SpanCapture):
    """Test tracing with dataclass as input."""
    from dataclasses import dataclass

    from uipath.core.tracing.decorators import traced

    @dataclass
    class Product:
        name: str
        price: float

    @traced(name="calculate_total")
    def calculate_total(product: Product, quantity: int):
        return product.price * quantity

    product = Product(name="Widget", price=9.99)
    result = calculate_total(product, 5)

    assert result == 49.95

    spans = span_capture.get_spans()
    assert len(spans) == 1

    span = spans[0]
    input_value = span.attributes.get("input.value")
    assert input_value is not None
    input_data = json.loads(input_value)
    assert input_data["product"]["name"] == "Widget"
    assert input_data["product"]["price"] == 9.99


def test_traced_with_enum_input(span_capture: SpanCapture):
    """Test tracing with enum as input."""
    from enum import Enum

    from uipath.core.tracing.decorators import traced

    class Status(Enum):
        PENDING = "pending"
        COMPLETED = "completed"

    @traced(name="update_status")
    def update_status(status: Status):
        return f"Status is {status.value}"

    result = update_status(Status.COMPLETED)

    assert result == "Status is completed"

    spans = span_capture.get_spans()
    assert len(spans) == 1

    span = spans[0]
    input_value = span.attributes.get("input.value")
    assert input_value is not None
    input_data = json.loads(input_value)
    assert input_data["status"] == "completed"


def test_traced_with_datetime_input(span_capture: SpanCapture):
    """Test tracing with datetime as input."""
    from datetime import datetime

    from uipath.core.tracing.decorators import traced

    @traced(name="process_timestamp")
    def process_timestamp(timestamp: datetime):
        return timestamp.isoformat()

    dt = datetime(2024, 1, 15, 10, 30, 0)
    process_timestamp(dt)

    spans = span_capture.get_spans()
    assert len(spans) == 1

    span = spans[0]
    input_value = span.attributes.get("input.value")
    assert input_value is not None
    input_data = json.loads(input_value)
    assert "2024-01-15" in input_data["timestamp"]


def test_traced_with_complex_return_value(span_capture: SpanCapture):
    """Test tracing with complex return value."""
    from typing import Any

    from pydantic import BaseModel

    from uipath.core.tracing.decorators import traced

    class Result(BaseModel):
        success: bool
        data: dict[str, Any]

    @traced(name="get_result")
    def get_result():
        return Result(success=True, data={"key": "value"})

    get_result()

    spans = span_capture.get_spans()
    assert len(spans) == 1

    span = spans[0]
    output_value = span.attributes.get("output.value")
    assert output_value is not None
    output_data = json.loads(output_value)
    assert output_data["success"] is True
    assert output_data["data"]["key"] == "value"


def test_traced_with_set_and_tuple(span_capture: SpanCapture):
    """Test tracing with set and tuple inputs."""
    from typing import Set, Tuple

    from uipath.core.tracing.decorators import traced

    @traced(name="process_collections")
    def process_collections(items: Set[int], pair: Tuple[int, ...]) -> int:
        return len(items) + len(pair)

    result = process_collections({1, 2, 3}, (4, 5))

    assert result == 5

    spans = span_capture.get_spans()
    assert len(spans) == 1

    span = spans[0]
    input_value = span.attributes.get("input.value")
    assert input_value is not None
    input_data = json.loads(input_value)
    # Sets and tuples should be converted to lists
    assert isinstance(input_data["items"], list)
    assert isinstance(input_data["pair"], list)
