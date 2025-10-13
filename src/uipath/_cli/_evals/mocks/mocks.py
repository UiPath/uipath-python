"""Mocking interface."""

import logging
from contextvars import ContextVar
from typing import Any, Callable, Optional

from uipath._cli._evals._models._evaluation_set import EvaluationItem
from uipath._cli._evals.mocks.mocker import Mocker, UiPathNoMockFoundError
from uipath._cli._evals.mocks.mocker_factory import MockerFactory

evaluation_context: ContextVar[Optional[EvaluationItem]] = ContextVar(
    "evaluation", default=None
)

mocker_context: ContextVar[Optional[Mocker]] = ContextVar("mocker", default=None)

logger = logging.getLogger(__name__)


def set_evaluation_item(item: EvaluationItem) -> None:
    """Set an evaluation item within an evaluation set."""
    evaluation_context.set(item)
    try:
        if item.mocking_strategy:
            mocker_context.set(MockerFactory.create(item))
        else:
            mocker_context.set(None)
    except Exception:
        logger.warning(f"Failed to create mocker for evaluation {item.name}")
        mocker_context.set(None)


async def get_mocked_response(
    func: Callable[[Any], Any], params: dict[str, Any], *args, **kwargs
) -> Any:
    """Get a mocked response."""
    mocker = mocker_context.get()
    if mocker is None:
        raise UiPathNoMockFoundError()
    else:
        return await mocker.response(func, params, *args, **kwargs)
