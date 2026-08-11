"""Agent demonstrating list targetOutputKey evaluation.

This agent simulates a product lookup: given a product ID it returns
a structured response with several fields. The evaluators use a list
of keys so that multiple fields can be asserted in a single evaluator
configuration, without comparing the entire output dict.
"""

from pydantic import BaseModel

CATALOG: dict[str, dict[str, object]] = {
    "p001": {
        "name": "Wireless Headphones",
        "price": 79.99,
        "category": "Electronics",
        "in_stock": True,
        "rating": 4.5,
    },
    "p002": {
        "name": "Running Shoes",
        "price": 120.0,
        "category": "Sports",
        "in_stock": False,
        "rating": 4.8,
    },
    "p003": {
        "name": "Coffee Maker",
        "price": 49.99,
        "category": "Kitchen",
        "in_stock": True,
        "rating": 4.2,
    },
}


class Input(BaseModel):
    """Input schema."""

    product_id: str


class Output(BaseModel):
    """Output schema."""

    name: str
    price: float
    category: str
    in_stock: bool
    rating: float


def main(input_data: Input) -> Output:
    """Look up a product by ID and return its details.

    Args:
        input_data: Input containing the product ID.

    Returns:
        Output with product details.

    Raises:
        ValueError: If the product ID is not found.
    """
    product = CATALOG.get(input_data.product_id)
    if product is None:
        raise ValueError(f"Product '{input_data.product_id}' not found")

    return Output(
        name=str(product["name"]),
        price=float(product["price"]),  # type: ignore[arg-type]
        category=str(product["category"]),
        in_stock=bool(product["in_stock"]),
        rating=float(product["rating"]),  # type: ignore[arg-type]
    )
