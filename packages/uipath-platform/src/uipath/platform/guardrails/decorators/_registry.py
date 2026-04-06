"""Adapter registry for guardrail target recognition and wrapping."""

from typing import Any, Protocol, runtime_checkable

from ._core import _EvaluatorFn
from ._enums import GuardrailExecutionStage
from ._models import GuardrailAction


@runtime_checkable
class GuardrailTargetAdapter(Protocol):
    """Protocol for framework-specific guardrail adapters.

    Implement this protocol to teach :func:`guardrail` how to handle objects
    from a particular framework. Register instances via
    :func:`register_guardrail_adapter`.
    """

    def recognize(self, target: Any) -> bool:
        """Return ``True`` if this adapter handles *target*.

        Args:
            target: Object being decorated or returned by a factory function.

        Returns:
            ``True`` if this adapter can wrap *target*, ``False`` otherwise.
        """
        ...

    def wrap(
        self,
        target: Any,
        evaluator: _EvaluatorFn,
        action: GuardrailAction,
        name: str,
        stage: GuardrailExecutionStage,
    ) -> Any:
        """Wrap *target* with guardrail enforcement logic.

        Args:
            target: Object to wrap.
            evaluator: Unified evaluation callable from :func:`_make_evaluator`.
            action: Action to invoke on validation failure.
            name: Human-readable guardrail name.
            stage: When to evaluate (PRE, POST, or PRE_AND_POST).

        Returns:
            Wrapped object, same type or duck-type compatible.
        """
        ...


# Module-level registry. Later-registered adapters take priority (inserted at 0).
_adapters: list[GuardrailTargetAdapter] = []


def register_guardrail_adapter(adapter: GuardrailTargetAdapter) -> None:
    """Register a framework adapter for the ``@guardrail`` decorator.

    Later-registered adapters are tried first.

    Args:
        adapter: An instance implementing :class:`GuardrailTargetAdapter`.
    """
    _adapters.insert(0, adapter)


def is_recognized_by_adapter(target: Any) -> bool:
    """Return ``True`` if any registered adapter recognizes *target*.

    Args:
        target: The object being decorated.

    Returns:
        ``True`` if a registered adapter handles *target*.
    """
    for adapter in _adapters:
        if adapter.recognize(target):
            return True
    return False


def wrap_with_adapter(
    target: Any,
    evaluator: _EvaluatorFn,
    action: GuardrailAction,
    name: str,
    stage: GuardrailExecutionStage,
) -> Any:
    """Ask the first matching adapter to wrap *target*.

    Args:
        target: The object to wrap.
        evaluator: Unified evaluation callable.
        action: Action on violation.
        name: Guardrail name.
        stage: Execution stage.

    Returns:
        Wrapped object, or *target* unchanged if no adapter handles it.
    """
    for adapter in _adapters:
        if adapter.recognize(target):
            return adapter.wrap(target, evaluator, action, name, stage)
    return target
