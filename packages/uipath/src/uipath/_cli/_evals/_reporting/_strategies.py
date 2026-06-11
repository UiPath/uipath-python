"""Strategy selection for StudioWeb evaluation reporting."""

from typing import Any

from uipath.eval.evaluators import BaseLegacyEvaluator
from uipath.eval.evaluators.base_evaluator import GenericBaseEvaluator

from ._coded_strategy import CodedEvalReportingStrategy
from ._legacy_strategy import LegacyEvalReportingStrategy
from ._strategy_protocol import EvalReportingStrategy

LEGACY_STRATEGY = LegacyEvalReportingStrategy()
CODED_STRATEGY = CodedEvalReportingStrategy()


def strategy_for(is_coded: bool) -> EvalReportingStrategy:
    """Return the reporting strategy for the given evaluation kind."""
    return CODED_STRATEGY if is_coded else LEGACY_STRATEGY


def is_coded_evaluators(
    evaluators: list[GenericBaseEvaluator[Any, Any, Any]],
) -> bool:
    """Check if evaluators are coded (BaseEvaluator) vs legacy (LegacyBaseEvaluator)."""
    if not evaluators:
        return False
    # Check the first evaluator type
    return not isinstance(evaluators[0], BaseLegacyEvaluator)
