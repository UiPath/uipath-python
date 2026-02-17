import logging
import random
from enum import Enum

from pydantic.dataclasses import dataclass

from uipath.tracing import traced

logger = logging.getLogger(__name__)


class Size(Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class CrustType(Enum):
    THIN = "thin"
    THICK = "thick"
    STUFFED = "stuffed"


@dataclass
class PizzaOrder:
    size: Size
    crust: CrustType
    toppings: list[str]
    quantity: int
    customer_name: str


@dataclass
class PriceBreakdown:
    base_price: float
    topping_surcharge: float
    crust_surcharge: float
    discount: float
    total: float


@dataclass
class OrderConfirmation:
    order_id: str
    price: PriceBreakdown
    estimated_minutes: int
    message: str


@traced()
async def generate_order_id() -> str:
    """Generate a unique order ID."""
    return f"PZA-{random.randint(1000, 9999)}"


@traced(name="log_step")
def log_step(step_name: str, details: str) -> None:
    """Log each processing step for auditing."""
    logger.info("[%s] %s", step_name, details)


@traced(name="calculate_base_price")
def calculate_base_price(size: Size, quantity: int) -> float:
    prices = {Size.SMALL: 8.99, Size.MEDIUM: 12.99, Size.LARGE: 16.99}
    log_step("base_price", f"{size.value} x{quantity}")
    return prices[size] * quantity


@traced(name="calculate_topping_surcharge")
def calculate_topping_surcharge(toppings: list[str], quantity: int) -> float:
    free_toppings = 2
    extra = max(0, len(toppings) - free_toppings)
    log_step("topping_surcharge", f"{len(toppings)} toppings, {extra} extra")
    return extra * 1.50 * quantity


@traced(name="calculate_crust_surcharge")
def calculate_crust_surcharge(crust: CrustType, quantity: int) -> float:
    surcharges = {CrustType.THIN: 0.0, CrustType.THICK: 1.00, CrustType.STUFFED: 2.50}
    log_step("crust_surcharge", f"{crust.value} crust")
    return surcharges[crust] * quantity


@traced(name="apply_discount")
def apply_discount(subtotal: float, quantity: int) -> float:
    if quantity >= 5:
        discount = subtotal * 0.15
    elif quantity >= 3:
        discount = subtotal * 0.10
    else:
        discount = 0.0
    log_step("discount", f"qty={quantity}, discount=${discount:.2f}")
    return discount


@traced(name="compute_price")
def compute_price(order: PizzaOrder) -> PriceBreakdown:
    base = calculate_base_price(order.size, order.quantity)
    topping = calculate_topping_surcharge(order.toppings, order.quantity)
    crust = calculate_crust_surcharge(order.crust, order.quantity)
    subtotal = base + topping + crust
    discount = apply_discount(subtotal, order.quantity)
    return PriceBreakdown(
        base_price=base,
        topping_surcharge=topping,
        crust_surcharge=crust,
        discount=discount,
        total=subtotal - discount,
    )


@traced(name="estimate_prep_time")
def estimate_prep_time(order: PizzaOrder) -> int:
    base_minutes = 15
    per_extra_pizza = 5
    stuffed_penalty = 7
    minutes = base_minutes + (order.quantity - 1) * per_extra_pizza
    if order.crust == CrustType.STUFFED:
        minutes += stuffed_penalty
    return minutes


@traced(name="format_confirmation")
def format_confirmation(
    order: PizzaOrder, order_id: str, price: PriceBreakdown, eta: int
) -> str:
    return (
        f"Hey {order.customer_name}! Order {order_id} confirmed. "
        f"{order.quantity}x {order.size.value} {order.crust.value} crust pizza "
        f"with {', '.join(order.toppings) or 'cheese only'}. "
        f"Total: ${price.total:.2f} (saved ${price.discount:.2f}). "
        f"Ready in ~{eta} min."
    )


@traced()
async def main(input: PizzaOrder) -> OrderConfirmation:
    order_id = await generate_order_id()
    price = compute_price(input)
    eta = estimate_prep_time(input)
    message = format_confirmation(input, order_id, price, eta)
    return OrderConfirmation(
        order_id=order_id,
        price=price,
        estimated_minutes=eta,
        message=message,
    )
