"""Mockito mocker implementation.

https://mockito-python.readthedocs.io/en/latest/
"""

from typing import Any, Callable

from hydra.utils import instantiate
from mockito import invocation, mocking  # type: ignore[import-untyped]

from uipath._cli._evals._models._evaluation_set import (
    EvaluationItem,
    MockingAnswerType,
    MockitoMockingStrategy,
)
from uipath._cli._evals.mocks.mocker import (
    Mocker,
    R,
    T,
    UiPathMockResponseGenerationError,
    UiPathNoMockFoundError,
)


class Stub:
    """Stub interface."""

    def __getattr__(self, item):
        """Return a wrapper function that raises an exception."""

        def func(*_args, **_kwargs):
            """Not Implemented."""
            raise NotImplementedError()

        return func


class MockitoMocker(Mocker):
    """Mockito Mocker."""

    def __init__(self, evaluation_item: EvaluationItem):
        """Instantiate a mockito mocker."""
        self.evaluation_item = evaluation_item
        assert isinstance(self.evaluation_item.mocking_strategy, MockitoMockingStrategy)

        self.stub = Stub()
        mock_obj = mocking.Mock(self.stub)

        for behavior in self.evaluation_item.mocking_strategy.behaviors:
            stubbed = invocation.StubbedInvocation(mock_obj, behavior.function)(
                *instantiate(behavior.arguments.args, _convert_="object"),
                **instantiate(behavior.arguments.kwargs, _convert_="object"),
            )
            for answer in behavior.then:
                if answer.type == MockingAnswerType.RETURN:
                    stubbed = stubbed.thenReturn(
                        instantiate(answer.model_dump(), _convert_="object")["value"]
                    )
                elif answer.type == MockingAnswerType.RAISE:
                    stubbed = stubbed.thenRaise(
                        instantiate(answer.model_dump(), _convert_="object")["value"]
                    )

    async def response(
        self, func: Callable[[T], R], params: dict[str, Any], *args: T, **kwargs
    ) -> R:
        """Respond with mocked response."""
        if not isinstance(
            self.evaluation_item.mocking_strategy, MockitoMockingStrategy
        ):
            raise UiPathMockResponseGenerationError("Mocking strategy misconfigured.")
        if not any(
            behavior.function == params["name"]
            for behavior in self.evaluation_item.mocking_strategy.behaviors
        ):
            raise UiPathNoMockFoundError()
        try:
            return getattr(self.stub, params["name"])(*args, **kwargs)
        except Exception as e:
            raise UiPathMockResponseGenerationError() from e
