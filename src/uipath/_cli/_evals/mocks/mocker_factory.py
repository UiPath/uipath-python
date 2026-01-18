"""Mocker Factory."""

from uipath._cli._evals.mocks.llm_mocker import LLMMocker
from uipath._cli._evals.mocks.mocker import Mocker
from uipath._cli._evals.mocks.mockito_mocker import MockitoMocker
from uipath._cli._evals.mocks.types import (
    LLMMockingStrategy,
    MockingContext,
    MockitoMockingStrategy,
)


class MockerFactory:
    """Mocker factory."""

    @staticmethod
    def create(context: MockingContext) -> Mocker:
        """Create a mocker instance."""
        match context.strategy:
            case LLMMockingStrategy():
                return LLMMocker(context)
            case MockitoMockingStrategy():
                return MockitoMocker(context)
            case _:
                raise ValueError("Unknown mocking strategy")
