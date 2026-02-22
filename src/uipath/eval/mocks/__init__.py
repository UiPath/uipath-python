"""Mock interface."""

from ._mocks import is_tool_simulated
from ._types import ExampleCall
from .mockable import mockable

__all__ = ["ExampleCall", "mockable", "is_tool_simulated"]
