"""Mocker Factory."""

from uipath.eval._models._evaluation_set import (
    EvaluationItem,
    LLMMockingStrategy,
    MockitoMockingStrategy,
)
from uipath.eval.mocks.llm_mocker import LLMMocker
from uipath.eval.mocks.mocker import Mocker
from uipath.eval.mocks.mockito_mocker import MockitoMocker


class MockerFactory:
    """Mocker factory."""

    @staticmethod
    def create(evaluation_item: EvaluationItem) -> Mocker:
        """Create a mocker instance."""
        match evaluation_item.mocking_strategy:
            case LLMMockingStrategy():
                return LLMMocker(evaluation_item)
            case MockitoMockingStrategy():
                return MockitoMocker(evaluation_item)
            case _:
                raise ValueError("Unknown mocking strategy")
