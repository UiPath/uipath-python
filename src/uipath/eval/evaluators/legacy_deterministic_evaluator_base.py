"""Base class for deterministic evaluators that provide consistent outputs."""

import json
from abc import ABC
from typing import Any, Generic, TypeVar

from .legacy_base_evaluator import LegacyBaseEvaluator, LegacyEvaluatorConfig

T = TypeVar("T", bound=LegacyEvaluatorConfig)


class DeterministicEvaluatorBase(LegacyBaseEvaluator[T], Generic[T], ABC):
    """Base class for evaluators that produce deterministic, reproducible results.

    This class provides utility methods for canonical JSON comparison and number normalization
    to ensure consistent evaluation results across runs.
    """

    def _canonical_json(self, obj: Any) -> str:
        """Convert an object to canonical JSON string for consistent comparison.

        Args:
            obj: The object to convert to canonical JSON

        Returns:
            str: Canonical JSON string with normalized numbers and sorted keys
        """
        return json.dumps(
            self._normalize_numbers(obj),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def _normalize_numbers(self, obj: Any) -> Any:
        """Recursively normalize numbers in nested data structures.

        Converts all numeric values (int, float) to float for consistent comparison,
        while preserving booleans and other data types.

        Args:
            obj: The object to normalize

        Returns:
            Any: Object with normalized numbers
        """
        if isinstance(obj, dict):
            return {k: self._normalize_numbers(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._normalize_numbers(v) for v in obj]
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            return float(obj)
        return obj
