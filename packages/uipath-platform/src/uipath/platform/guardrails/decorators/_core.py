"""Core framework-agnostic utilities for guardrail decorators."""

import ast
import dataclasses
import inspect
import json
import logging
from typing import Annotated, Any, Callable, get_args, get_origin, get_type_hints

from uipath.core.guardrails import (
    GuardrailValidationResult,
)

from ._enums import GuardrailExecutionStage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GuardrailExclude marker
# ---------------------------------------------------------------------------


class GuardrailExclude:
    """Marker to exclude a parameter from guardrail input serialization.

    Use with :data:`typing.Annotated` to prevent a specific function parameter
    from being collected into the guardrail evaluation payload::

        async def process(
            text: str,
            config: Annotated[dict, GuardrailExclude()],
        ) -> str: ...
    """


# ---------------------------------------------------------------------------
# Evaluator type alias
# ---------------------------------------------------------------------------

_EvaluatorFn = Callable[
    [
        "str | dict[str, Any]",  # data
        GuardrailExecutionStage,  # stage
        "dict[str, Any] | None",  # input_data
        "dict[str, Any] | None",  # output_data
    ],
    GuardrailValidationResult,
]
"""Type alias for the unified evaluation callable used by all wrappers."""


# ---------------------------------------------------------------------------
# Evaluator factory
# ---------------------------------------------------------------------------


def _make_evaluator(
    validator: Any,
    name: str,
    description: str | None,
    enabled_for_evals: bool,
) -> _EvaluatorFn:
    """Return a unified evaluation callable.

    Delegates to ``validator.run()`` which each validator subclass implements
    (:class:`BuiltInGuardrailValidator` hits the UiPath API;
    :class:`CustomGuardrailValidator` runs a local Python rule).

    Args:
        validator: :class:`GuardrailValidatorBase` instance.
        name: Guardrail name — forwarded to ``validator.run()`` on each call.
        description: Optional description — forwarded to ``validator.run()``.
        enabled_for_evals: Whether active in evaluation scenarios.

    Returns:
        Callable with signature ``(data, stage, input_data, output_data)``.
    """

    def _eval(
        data: str | dict[str, Any],
        stage: GuardrailExecutionStage,
        input_data: dict[str, Any] | None,
        output_data: dict[str, Any] | None,
    ) -> GuardrailValidationResult:
        return validator.run(
            name, description, enabled_for_evals, data, stage, input_data, output_data
        )

    return _eval


# ---------------------------------------------------------------------------
# Parameter introspection
# ---------------------------------------------------------------------------


def _get_excluded_params(func: Any) -> set[str]:
    """Return parameter names annotated with :class:`GuardrailExclude`.

    Args:
        func: Callable to inspect.

    Returns:
        Set of parameter names that should be excluded from guardrail input.
    """
    try:
        hints = get_type_hints(func, include_extras=True)
    except Exception:
        return set()
    excluded: set[str] = set()
    for name, hint in hints.items():
        if get_origin(hint) is Annotated:
            for meta in get_args(hint)[1:]:
                if isinstance(meta, GuardrailExclude):
                    excluded.add(name)
    return excluded


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_value(value: Any) -> Any:
    """Serialize *value* to a JSON-compatible type for guardrail evaluation.

    Pydantic models → ``model_dump()``, dataclasses → ``asdict()``,
    primitives → as-is, everything else → ``str()``.
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    # Pydantic v2
    if hasattr(value, "model_dump"):
        return value.model_dump()
    # Pydantic v1
    if hasattr(value, "dict") and callable(value.dict):
        try:
            return value.dict()
        except Exception:
            pass
    # dataclasses
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    return str(value)


def _collect_input(
    bound: inspect.BoundArguments,
    excluded: set[str],
) -> dict[str, Any]:
    """Collect non-excluded function parameters into a guardrail input dict.

    Args:
        bound: Bound arguments from ``inspect.Signature.bind()``.
        excluded: Parameter names to skip.

    Returns:
        ``{param_name: serialized_value}`` for all non-excluded parameters.
    """
    result: dict[str, Any] = {}
    for name, value in bound.arguments.items():
        if name in excluded or name in ("self", "cls"):
            continue
        result[name] = _serialize_value(value)
    return result


def _collect_output(return_value: Any) -> dict[str, Any]:
    """Serialize a function return value into a dict for guardrail evaluation.

    Args:
        return_value: The value returned by the wrapped function.

    Returns:
        A ``dict`` representation suitable for guardrail evaluation.
    """
    serialized = _serialize_value(return_value)
    if isinstance(serialized, dict):
        return serialized
    return {"return": serialized}


def _reconstruct_output(original: Any, modified: Any) -> Any:
    """Reconstruct a return value from a guardrail-modified payload.

    Args:
        original: The original return value (used to determine target type).
        modified: The modified value returned by the guardrail action.

    Returns:
        Reconstructed value of the same type as *original* where possible.
    """
    if modified is None:
        return original
    # Pydantic v2 model + dict modification → reconstruct via model_validate
    if hasattr(original, "model_validate") and isinstance(modified, dict):
        try:
            return type(original).model_validate(modified)
        except Exception:
            pass
    # Pydantic v1
    if hasattr(original, "parse_obj") and isinstance(modified, dict):
        try:
            return type(original).parse_obj(modified)
        except Exception:
            pass
    return modified


def _apply_pre_modification(
    bound: inspect.BoundArguments,
    modified: Any,
    excluded: set[str],
) -> None:
    """Apply guardrail PRE-stage modifications back to bound function arguments.

    If the action returned a modified dict, keys matching non-excluded parameters
    are updated in-place. If the action returned a plain string and there is exactly
    one non-excluded parameter, that parameter is updated.

    Args:
        bound: Bound arguments to mutate in-place.
        modified: Value returned by the guardrail action.
        excluded: Parameter names that were excluded from evaluation.
    """
    if modified is None:
        return
    non_excluded = [
        n for n in bound.arguments if n not in excluded and n not in ("self", "cls")
    ]
    if isinstance(modified, dict):
        for name in non_excluded:
            if name in modified:
                bound.arguments[name] = modified[name]
    elif isinstance(modified, str) and len(non_excluded) == 1:
        bound.arguments[non_excluded[0]] = modified


# ---------------------------------------------------------------------------
# Tool I/O normalisation helpers (used by LangChain adapter)
# ---------------------------------------------------------------------------


def _is_tool_call_envelope(tool_input: Any) -> bool:
    """Return ``True`` if *tool_input* is a LangGraph tool-call envelope dict."""
    return (
        isinstance(tool_input, dict)
        and "args" in tool_input
        and tool_input.get("type") == "tool_call"
    )


def _extract_input(tool_input: Any) -> dict[str, Any]:
    """Normalise tool input to a plain dict for rule / guardrail evaluation.

    LangGraph wraps tool inputs as ``{"name": ..., "args": {...}, "type": "tool_call"}``.
    This function unwraps ``args`` so rules can access the actual tool arguments.
    """
    if _is_tool_call_envelope(tool_input):
        args = tool_input["args"]
        if isinstance(args, dict):
            return args
    if isinstance(tool_input, dict):
        return tool_input
    return {"input": tool_input}


def _rewrap_input(original_tool_input: Any, modified_args: dict[str, Any]) -> Any:
    """Re-wrap modified args back into the original tool-call envelope (if applicable)."""
    if _is_tool_call_envelope(original_tool_input):
        import copy

        wrapped = copy.copy(original_tool_input)
        wrapped["args"] = modified_args
        return wrapped
    return modified_args


def _extract_output(result: Any) -> dict[str, Any]:
    """Normalise tool output to a dict for guardrail / rule evaluation.

    Falls back to ``{"output": content}`` for plain strings and anything else.
    """
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            return parsed if isinstance(parsed, dict) else {"output": parsed}
        except ValueError:
            try:
                parsed = ast.literal_eval(result)
                return parsed if isinstance(parsed, dict) else {"output": parsed}
            except (ValueError, SyntaxError):
                return {"output": result}
    return {"output": result}
