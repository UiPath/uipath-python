"""UiPath evaluation module for agent performance assessment."""

import warnings
from typing import Any

from uipath.eval.models.models import (
    BooleanEvaluationResult,
    ErrorEvaluationResult,
    EvalItemResult,
    EvaluationResult,
    EvaluationResultDto,
    EvaluatorType,
    LegacyEvaluatorCategory,
    LegacyEvaluatorType,
    LLMResponse,
    NumericEvaluationResult,
    ScoreType,
    ToolCall,
    ToolOutput,
    WorkloadExecution,
)

__all__ = [
    "WorkloadExecution",
    "EvaluationResult",
    "EvaluationResultDto",
    "LLMResponse",
    "LegacyEvaluatorCategory",
    "LegacyEvaluatorType",
    "EvaluatorType",
    "ScoreType",
    "EvalItemResult",
    "BooleanEvaluationResult",
    "NumericEvaluationResult",
    "ErrorEvaluationResult",
    "ToolCall",
    "ToolOutput",
]

# Backward-compatibility shim: ``AgentExecution`` was renamed to
# ``WorkloadExecution``. The old name keeps working but emits a
# DeprecationWarning. Remove in uipath 3.0.
_DEPRECATED_NAMES = {"AgentExecution": "WorkloadExecution"}


def __getattr__(name: str) -> Any:
    new_name = _DEPRECATED_NAMES.get(name)
    if new_name is not None:
        warnings.warn(
            f"{name} is deprecated and will be removed in uipath 3.0; "
            f"use {new_name} instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return globals()[new_name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
