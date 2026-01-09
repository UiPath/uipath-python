"""Mock interface."""

from uipath._cli._evals._models._mocks import ExampleCall
from uipath._cli._evals.mocks.mocks import is_tool_simulated

from .mockable import mockable

__all__ = ["ExampleCall", "mockable", "is_tool_simulated"]
