"""Mocker Factory."""

from ._llm_mocker import LLMMocker
from ._mocker import Mocker
from ._mockito_mocker import MockitoMocker
from ._simulate_component_mocker import SimulateComponentMocker
from ._types import (
    LLMMockingStrategy,
    MockingContext,
    MockitoMockingStrategy,
)


class MockerFactory:
    """Mocker factory."""

    @staticmethod
    def create(context: MockingContext) -> Mocker:
        """Create a mocker instance."""
        if context.components:
            return SimulateComponentMocker(context)
        match context.strategy:
            case LLMMockingStrategy():
                return LLMMocker(context)
            case MockitoMockingStrategy():
                return MockitoMocker(context)
            case _:
                raise ValueError("Unknown mocking strategy")
