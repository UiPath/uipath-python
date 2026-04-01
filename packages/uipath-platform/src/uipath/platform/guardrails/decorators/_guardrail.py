"""Single ``@guardrail`` decorator for all guardrail types."""

import inspect
import logging
from functools import wraps
from typing import Any

from ._core import (
    _apply_pre_modification,
    _collect_input,
    _collect_output,
    _EvaluatorFn,
    _get_excluded_params,
    _make_evaluator,
    _reconstruct_output,
)
from ._enums import GuardrailExecutionStage
from ._models import GuardrailAction
from ._registry import is_recognized_by_adapter, wrap_with_adapter
from .validators._base import GuardrailValidatorBase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_pre(
    evaluator: _EvaluatorFn,
    action: GuardrailAction,
    name: str,
    bound: inspect.BoundArguments,
    excluded: set[str],
) -> None:
    """Evaluate PRE guardrail and apply any modifications to *bound* in-place."""
    input_data = _collect_input(bound, excluded)
    try:
        result = evaluator(input_data, GuardrailExecutionStage.PRE, input_data, None)
    except Exception as exc:
        logger.error("Error evaluating PRE guardrail %r: %s", name, exc, exc_info=True)
        return
    from uipath.core.guardrails import GuardrailValidationResultType

    if result.result == GuardrailValidationResultType.VALIDATION_FAILED:
        modified = action.handle_validation_result(result, input_data, name)
        _apply_pre_modification(bound, modified, excluded)


def _run_post(
    evaluator: _EvaluatorFn,
    action: GuardrailAction,
    name: str,
    bound: inspect.BoundArguments,
    excluded: set[str],
    return_value: Any,
) -> Any:
    """Evaluate POST guardrail and return (possibly modified) return value."""
    input_data = _collect_input(bound, excluded)
    output_data = _collect_output(return_value)
    try:
        result = evaluator(
            output_data, GuardrailExecutionStage.POST, input_data, output_data
        )
    except Exception as exc:
        logger.error("Error evaluating POST guardrail %r: %s", name, exc, exc_info=True)
        return return_value
    from uipath.core.guardrails import GuardrailValidationResultType

    if result.result == GuardrailValidationResultType.VALIDATION_FAILED:
        modified = action.handle_validation_result(result, output_data, name)
        return _reconstruct_output(return_value, modified)
    return return_value


def _wrap_function(
    func: Any,
    evaluator: _EvaluatorFn,
    action: GuardrailAction,
    name: str,
    stage: GuardrailExecutionStage,
    excluded: set[str],
) -> Any:
    """Wrap *func* as a pure Python function with PRE/POST guardrail evaluation."""
    sig = inspect.signature(func)

    def _dispatch_return(return_value: Any) -> Any:
        """For factory functions: if the return value is recognized by an adapter, wrap it."""
        if is_recognized_by_adapter(return_value):
            return wrap_with_adapter(return_value, evaluator, action, name, stage)
        return return_value

    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def _wrapped_async(*args: Any, **kwargs: Any) -> Any:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            if stage in (
                GuardrailExecutionStage.PRE,
                GuardrailExecutionStage.PRE_AND_POST,
            ):
                _run_pre(evaluator, action, name, bound, excluded)
            return_value = await func(*bound.args, **bound.kwargs)
            return_value = _dispatch_return(return_value)
            if stage in (
                GuardrailExecutionStage.POST,
                GuardrailExecutionStage.PRE_AND_POST,
            ):
                # Only run POST on plain (non-adapter-wrapped) values
                if not is_recognized_by_adapter(return_value):
                    return_value = _run_post(
                        evaluator, action, name, bound, excluded, return_value
                    )
            return return_value

        return _wrapped_async

    @wraps(func)
    def _wrapped(*args: Any, **kwargs: Any) -> Any:
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        if stage in (
            GuardrailExecutionStage.PRE,
            GuardrailExecutionStage.PRE_AND_POST,
        ):
            _run_pre(evaluator, action, name, bound, excluded)
        return_value = func(*bound.args, **bound.kwargs)
        return_value = _dispatch_return(return_value)
        if stage in (
            GuardrailExecutionStage.POST,
            GuardrailExecutionStage.PRE_AND_POST,
        ):
            if not is_recognized_by_adapter(return_value):
                return_value = _run_post(
                    evaluator, action, name, bound, excluded, return_value
                )
        return return_value

    return _wrapped


# ---------------------------------------------------------------------------
# Public @guardrail decorator
# ---------------------------------------------------------------------------


def guardrail(
    func: Any = None,
    *,
    validator: GuardrailValidatorBase,
    action: GuardrailAction,
    name: str = "Guardrail",
    description: str | None = None,
    stage: GuardrailExecutionStage = GuardrailExecutionStage.PRE_AND_POST,
    enabled_for_evals: bool = True,
) -> Any:
    """Apply a guardrail to any callable — tool functions, LLM factories, agent nodes.

    When applied to a plain function or async function, the decorator collects
    function parameters (PRE) and return value (POST) and evaluates them against
    the guardrail. Use :class:`~._core.GuardrailExclude` to opt individual
    parameters out of serialization.

    When applied to a factory function whose return value is recognised by a
    registered framework adapter (e.g. a LangChain ``BaseChatModel``), the
    returned object is wrapped so every subsequent ``invoke()`` call is guarded.

    Multiple ``@guardrail`` decorators can be stacked on the same callable.

    Args:
        func: Callable to decorate. Supplied directly when used without parentheses.
        validator: :class:`~.validators.GuardrailValidatorBase` defining what to check.
        action: :class:`~._models.GuardrailAction` defining how to respond on violation.
        name: Human-readable name for this guardrail instance.
        description: Optional description passed to API-based guardrails.
        stage: When to evaluate — ``PRE``, ``POST``, or ``PRE_AND_POST``.
            Defaults to ``PRE_AND_POST``.
        enabled_for_evals: Whether this guardrail is active in evaluation scenarios.
            Defaults to ``True``.

    Returns:
        The decorated callable (or framework object).

    Raises:
        ValueError: If *action* is invalid, or the validator does not support
            the requested stage.
        GuardrailBlockException: Raised at runtime by :class:`~._actions.BlockAction`
            when a violation is detected.
    """
    if action is None:
        raise ValueError("action must be provided")
    if not isinstance(action, GuardrailAction):
        raise ValueError("action must be an instance of GuardrailAction")
    if not isinstance(enabled_for_evals, bool):
        raise ValueError("enabled_for_evals must be a boolean")

    def _apply(obj: Any) -> Any:
        # ------------------------------------------------------------------
        # 1. Adapter-recognised direct object (e.g. BaseTool after @tool)
        # ------------------------------------------------------------------
        if is_recognized_by_adapter(obj):
            validator.validate_stage(stage)
            evaluator = _make_evaluator(validator, name, description, enabled_for_evals)
            return wrap_with_adapter(obj, evaluator, action, name, stage)

        # ------------------------------------------------------------------
        # 2. Plain callable — wrap as pure function
        # ------------------------------------------------------------------
        if callable(obj):
            validator.validate_stage(stage)
            evaluator = _make_evaluator(validator, name, description, enabled_for_evals)
            excluded = _get_excluded_params(obj)
            return _wrap_function(obj, evaluator, action, name, stage, excluded)

        raise ValueError(
            f"@guardrail cannot be applied to {type(obj)!r}. "
            "Target must be a callable or a framework-registered object. "
            "Ensure the relevant framework adapter is imported before using @guardrail."
        )

    if func is None:
        return _apply
    return _apply(func)
