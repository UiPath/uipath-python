"""Mockito mocker implementation. https://mockito-python.readthedocs.io/en/latest ."""

from typing import Any, Callable

from mockito import (  # type: ignore[import-untyped] # explicit ignore
    invocation,
    mocking,
)

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
)


class Stub:
    """Stub interface."""

    def __getattr__(self, item):
        """Return a wrapper function that raises an exception."""

        def func(*_args, **_kwargs):
            raise NotImplementedError()

        return func


def _resolve_value(config: Any) -> Any:
    # Handle {"_attr_": "mockito.any"}
    if isinstance(config, dict) and "_attr_" in config:
        attr = config["_attr_"]
        if attr == "mockito.any":
            from mockito import any as mockito_any

            return mockito_any()

    # Handle {"_target_": "..."}
    if isinstance(config, dict) and "_target_" in config:
        target = config["_target_"]
        module_path, name = target.rsplit(".", 1)

        import importlib

        module = importlib.import_module(module_path)
        obj = getattr(module, name)

        args = [_resolve_value(v) for v in config.get("_args_", [])]
        kwargs = {
            k: _resolve_value(v)
            for k, v in config.items()
            if k not in ("_target_", "_args_")
        }
        return obj(*args, **kwargs)

    if isinstance(config, dict):
        return {k: _resolve_value(v) for k, v in config.items()}

    if isinstance(config, list):
        return [_resolve_value(v) for v in config]

    if isinstance(config, tuple):
        return tuple(_resolve_value(v) for v in config)

    return config


class MockitoMocker(Mocker):
    """Mockito Mocker."""

    def __init__(self, evaluation_item: EvaluationItem):
        """Instantiate a mockito mocker."""
        self.evaluation_item = evaluation_item
        assert isinstance(self.evaluation_item.mocking_strategy, MockitoMockingStrategy)

        self.stub = Stub()
        mock_obj = mocking.Mock(self.stub)

        for behavior in self.evaluation_item.mocking_strategy.behaviors:
            resolved_args = _resolve_value(behavior.arguments.args)
            resolved_kwargs = _resolve_value(behavior.arguments.kwargs)

            args = resolved_args if resolved_args is not None else []
            kwargs = resolved_kwargs if resolved_kwargs is not None else {}

            stubbed = invocation.StubbedInvocation(mock_obj, behavior.function)(
                *args,
                **kwargs,
            )

            for answer in behavior.then:
                answer_dict = answer.model_dump()

                if answer.type == MockingAnswerType.RETURN:
                    stubbed = stubbed.thenReturn(_resolve_value(answer_dict["value"]))

                elif answer.type == MockingAnswerType.RAISE:
                    stubbed = stubbed.thenRaise(_resolve_value(answer_dict["value"]))

    async def response(
        self, func: Callable[[T], R], params: dict[str, Any], *args: T, **kwargs
    ) -> R:
        """Return mocked response or raise appropriate errors."""
        if not isinstance(
            self.evaluation_item.mocking_strategy, MockitoMockingStrategy
        ):
            raise UiPathMockResponseGenerationError("Mocking strategy misconfigured.")

        # No behavior configured → call real function
        is_mocked = any(
            behavior.function == params["name"]
            for behavior in self.evaluation_item.mocking_strategy.behaviors
        )

        if not is_mocked:
            import inspect

            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            return func(*args, **kwargs)

        # Behavioral mocking
        try:
            return getattr(self.stub, params["name"])(*args, **kwargs)

        except NotImplementedError:
            raise

        except Exception as e:
            raise UiPathMockResponseGenerationError() from e
