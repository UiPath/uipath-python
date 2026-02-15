"""Multi-output agent for testing targetOutputKey path resolution.

This agent returns a complex nested output with multiple properties,
nested objects, and arrays of objects - designed to test evaluator
targetOutputKey with dot-notation and bracket-index paths.
"""

from pydantic.dataclasses import dataclass

from uipath.tracing import traced


@dataclass
class OrderItem:
    name: str
    quantity: int
    price: float


@dataclass
class Address:
    street: str
    city: str
    zip_code: str


@dataclass
class Customer:
    name: str
    email: str
    address: Address


@dataclass
class OrderInput:
    customer_name: str
    items: list[dict[str, object]]


@dataclass
class OrderSummary:
    total: float
    item_count: int
    status: str


@dataclass
class OrderOutput:
    order_id: str
    customer: Customer
    items: list[OrderItem]
    summary: OrderSummary
    tags: list[str]


@traced()
async def main(input: OrderInput) -> OrderOutput:
    """Process an order and return a complex nested output."""
    items = [
        OrderItem(
            name=str(item.get("name", "")),
            quantity=int(item.get("quantity", 0)),
            price=float(item.get("price", 0.0)),
        )
        for item in input.items
    ]

    total = sum(item.price * item.quantity for item in items)
    item_count = sum(item.quantity for item in items)

    return OrderOutput(
        order_id="ORD-001",
        customer=Customer(
            name=input.customer_name,
            email=f"{input.customer_name.lower().replace(' ', '.')}@example.com",
            address=Address(
                street="123 Main St",
                city="Springfield",
                zip_code="62701",
            ),
        ),
        items=items,
        summary=OrderSummary(
            total=total,
            item_count=item_count,
            status="completed",
        ),
        tags=["priority", "express", "verified"],
    )
