"""Mock interface."""

from ._mock_context import is_tool_simulated
from ._mock_runtime import UiPathMockRuntime
from ._types import ExampleCall, MockingContext
from .mockable import mockable

__all__ = [
    "ExampleCall",
    "UiPathMockRuntime",
    "MockingContext",
    "mockable",
    "is_tool_simulated",
]
