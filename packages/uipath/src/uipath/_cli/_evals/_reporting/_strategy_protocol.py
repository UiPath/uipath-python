"""Protocol for evaluation reporting strategies.

Strategies encapsulate the differences between the legacy and coded
StudioWeb evaluation APIs: endpoint routing (``coded/`` segment), ID
conversion (legacy requires GUIDs), eval snapshot shape, result collection
format, and the update payload structure.
"""

from typing import Any, Protocol, runtime_checkable

from uipath.eval.models import EvalItemResult
from uipath.eval.models.evaluation_set import EvaluationItem


@runtime_checkable
class EvalReportingStrategy(Protocol):
    """Strategy for one of the StudioWeb evaluation API formats."""

    @property
    def endpoint_suffix(self) -> str:
        """Endpoint path segment: ``""`` for legacy, ``"coded/"`` for coded."""
        ...

    def convert_id(self, id_value: str) -> str:
        """Convert an ID to the format the backend expects.

        Legacy: deterministic GUID (uuid5) for non-GUID strings.
        Coded: the original string ID unchanged.
        """
        ...

    def build_eval_snapshot(self, eval_item: EvaluationItem) -> dict[str, Any]:
        """Build the ``evalSnapshot`` payload for creating an eval run."""
        ...

    def collect_results(
        self,
        eval_results: list[EvalItemResult],
        evaluators: dict[str, Any],
        usage_metrics: dict[str, int | float | None],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect evaluator runs and scores in this format's shape.

        Results whose evaluator is not in ``evaluators`` are skipped (mixed
        coded/legacy eval sets are processed by both strategies).

        Returns:
            A tuple of (evaluator/assertion runs, evaluator scores).
        """
        ...

    def build_update_eval_run_payload(
        self,
        runs: list[dict[str, Any]],
        scores: list[dict[str, Any]],
        eval_run_id: str,
        actual_output: dict[str, Any],
        execution_time: float,
        status: int,
    ) -> dict[str, Any]:
        """Build the PUT evalRun payload (shape differs between formats)."""
        ...
