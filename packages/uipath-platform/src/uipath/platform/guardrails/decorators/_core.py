"""Core framework-agnostic utilities for guardrail decorators."""

import ast
import dataclasses
import inspect
import json
import logging
from typing import Annotated, Any, Protocol, get_args, get_origin, get_type_hints

from uipath.core.guardrails import (
    GuardrailValidationResult,
)

from ..attachments import (
    DetectionScope,
    detection_scope_includes_files,
    discover_attachments,
    with_detection_scope,
)
from ..guardrails import GuardrailAttachment
from ._enums import GuardrailExecutionStage
from .validators._base import BuiltInGuardrailValidator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GuardrailExclude marker
# ---------------------------------------------------------------------------


class GuardrailExclude:
    """Marker to exclude a parameter from guardrail input serialization.

    Use with `typing.Annotated` to prevent a specific function parameter
    from being collected into the guardrail evaluation payload:

        async def process(
            text: str,
            config: Annotated[dict, GuardrailExclude()],
        ) -> str: ...
    """


# ---------------------------------------------------------------------------
# Evaluator type alias
# ---------------------------------------------------------------------------


class _EvaluatorFn(Protocol):
    """The unified evaluation callable used by all wrappers.

    ``attachments`` is keyword-only and optional, so adapters that call
    ``evaluator(data, stage, input_data, output_data)`` keep working.

    Adapters may also read an optional ``forwards_attachments`` attribute, which
    is not a member of this Protocol. `_make_evaluator` sets it to False when the
    evaluator drops every attachment (text scope, or a validator that takes no
    files), so a call with files but no text can be skipped. An evaluator without
    it counts as forwarding: ``getattr(evaluator, "forwards_attachments", True)``.
    """

    def __call__(
        self,
        data: str | dict[str, Any],
        stage: GuardrailExecutionStage,
        input_data: dict[str, Any] | None,
        output_data: dict[str, Any] | None,
        *,
        attachments: list[GuardrailAttachment] | None = None,
    ) -> GuardrailValidationResult: ...


# ---------------------------------------------------------------------------
# Evaluator factory
# ---------------------------------------------------------------------------


def _accepts_files(validator: BuiltInGuardrailValidator) -> bool:
    """Tell whether ``run`` takes ``attachments`` and ``detection_scope`` or ``**kwargs``."""
    try:
        parameters = inspect.signature(type(validator).run).parameters.values()
    except (AttributeError, TypeError, ValueError):
        return False
    names = {parameter.name for parameter in parameters}
    return {"attachments", "detection_scope"} <= names or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters
    )


def _detection_scope_admits_files(
    validator: BuiltInGuardrailValidator,
    name: str,
    description: str | None,
    enabled_for_evals: bool,
    detection_scope: DetectionScope | None,
) -> bool:
    """Tell whether the detection scope lets files through; unreadable means yes."""
    if detection_scope == DetectionScope.TEXT:
        return False
    try:
        built_in = validator.get_built_in_guardrail(
            name, description, enabled_for_evals
        )
        return detection_scope_includes_files(
            with_detection_scope(built_in, detection_scope)
        )
    except Exception:
        return True


def _run_kwargs(
    detection_scope: DetectionScope | None,
    attachments: list[GuardrailAttachment] | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if detection_scope is not None:
        kwargs["detection_scope"] = detection_scope
    if attachments is not None and detection_scope != DetectionScope.TEXT:
        kwargs["attachments"] = list(attachments)
    return kwargs


def _make_evaluator(
    validator: Any,
    name: str,
    description: str | None,
    enabled_for_evals: bool,
    detection_scope: DetectionScope | None = None,
) -> _EvaluatorFn:
    """Return a unified evaluation callable.

    Delegates to ``validator.run()`` which each validator subclass implements
    (`BuiltInGuardrailValidator` hits the UiPath API;
    `CustomGuardrailValidator` runs a local Python rule). Only a
    `BuiltInGuardrailValidator` whose ``run`` takes ``attachments`` and
    ``detection_scope`` (or ``**kwargs``) receives the detection scope and the
    attachments; other validators are called with the original positional
    arguments, and a built-in one that overrides ``run`` without them is warned
    about once.

    Args:
        validator: `GuardrailValidatorBase` instance.
        name: Guardrail name — forwarded to ``validator.run()`` on each call.
        description: Optional description — forwarded to ``validator.run()``.
        enabled_for_evals: Whether active in evaluation scenarios.
        detection_scope: Sent to the API, or None to send none (text only).

    Returns:
        Callable with signature
        ``(data, stage, input_data, output_data, *, attachments=None)`` and a
        ``forwards_attachments`` attribute.
    """
    built_in = isinstance(validator, BuiltInGuardrailValidator)
    forwards_files = built_in and _accepts_files(validator)
    warned = False
    if detection_scope is not None and not built_in:
        logger.warning(
            "Guardrail '%s' sets detection_scope, but %s evaluates locally and "
            "never reads files; the detection scope is ignored.",
            name,
            type(validator).__name__,
        )

    def _eval(
        data: str | dict[str, Any],
        stage: GuardrailExecutionStage,
        input_data: dict[str, Any] | None,
        output_data: dict[str, Any] | None,
        *,
        attachments: list[GuardrailAttachment] | None = None,
    ) -> GuardrailValidationResult:
        nonlocal warned
        if built_in and not forwards_files and not warned:
            warned = True
            logger.warning(
                "Validator %s overrides run() without the attachments/detection_scope "
                "parameters; files and the detection scope are ignored for guardrail "
                "'%s'.",
                type(validator).__name__,
                name,
            )
        if forwards_files:
            return validator.run(
                name,
                description,
                enabled_for_evals,
                data,
                stage,
                input_data,
                output_data,
                **_run_kwargs(detection_scope, attachments),
            )
        return validator.run(
            name, description, enabled_for_evals, data, stage, input_data, output_data
        )

    forwards_attachments = forwards_files and _detection_scope_admits_files(
        validator, name, description, enabled_for_evals, detection_scope
    )
    _eval.forwards_attachments = forwards_attachments  # type: ignore[attr-defined]
    return _eval


# ---------------------------------------------------------------------------
# Parameter introspection
# ---------------------------------------------------------------------------


def _get_excluded_params(func: Any) -> set[str]:
    """Return parameter names annotated with `GuardrailExclude`.

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

    Pydantic models → ``model_dump(mode="json")`` (the plain ``model_dump()``
    when a field has no JSON form), dataclasses → ``asdict()``, primitives →
    as-is, everything else → ``str()``.
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
        try:
            return value.model_dump(mode="json")
        except Exception:
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


def _discover_input_attachments(
    bound: inspect.BoundArguments,
    excluded: set[str],
) -> list[GuardrailAttachment] | None:
    """Return references for the attachments among the non-excluded arguments.

    Args:
        bound: Bound arguments from ``inspect.Signature.bind()``, scanned raw.
        excluded: Parameter names to skip.

    Returns:
        The references to forward; empty when there are none; ``None`` when the
        arguments cannot be scanned.
    """
    try:
        return discover_attachments(
            {
                name: value
                for name, value in bound.arguments.items()
                if name not in excluded and name not in ("self", "cls")
            }
        )
    except Exception:
        logger.warning("Could not scan the arguments for attachments.", exc_info=True)
        return None


def _discover_output_attachments(
    return_value: Any,
) -> list[GuardrailAttachment] | None:
    """Return references for the attachments in a function's return value.

    Args:
        return_value: The value returned by the wrapped function, scanned raw.

    Returns:
        The references to forward; empty when there are none; ``None`` when the
        value cannot be scanned.
    """
    try:
        return discover_attachments(return_value)
    except Exception:
        logger.warning(
            "Could not scan the return value for attachments.", exc_info=True
        )
        return None


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
