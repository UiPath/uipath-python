"""Mocker Factory."""

from uipath._cli._evals.mocks.llm_mocker import LLMMocker
from uipath._cli._evals.mocks.mocker import Mocker
from uipath._cli._evals.mocks.mockito_mocker import MockitoMocker
from uipath._cli._evals.mocks.strategy import (
    LLMMockingStrategy,
    MockingStrategy,
    MockitoMockingStrategy,
)


class MockerFactory:
    """Mocker factory."""

    @staticmethod
    def create(strategy: MockingStrategy) -> Mocker:
        """Create a mocker instance."""
        match strategy:
            case LLMMockingStrategy():
                return LLMMocker(strategy)
            case MockitoMockingStrategy():
                return MockitoMocker(strategy)
            case _:
                raise ValueError("Unknown mocking strategy")
