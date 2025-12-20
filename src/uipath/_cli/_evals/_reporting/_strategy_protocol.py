"""Protocol definition for evaluation reporting strategies.

This module defines the Strategy Protocol for handling the differences between
legacy and coded evaluation API formats.
"""

from typing import Any, Callable, Protocol, runtime_checkable

from uipath._cli._evals._models._evaluation_set import EvaluationItem
from uipath._cli._evals._models._sw_reporting import StudioWebAgentSnapshot


@runtime_checkable
class EvalReportingStrategy(Protocol):
    """Protocol for evaluation reporting strategies.

    Strategies handle the differences between legacy and coded evaluation
    API formats, including ID conversion, endpoint routing, and payload structure.
    """

    @property
    def endpoint_suffix(self) -> str:
        """Return the endpoint suffix for this strategy.

        Returns:
            "" for legacy, "coded/" for coded evaluations
        """
        ...

    def convert_id(self, id_value: str) -> str:
        """Convert an ID to the format expected by the backend.

        Args:
            id_value: The original string ID

        Returns:
            For legacy: deterministic GUID from uuid5
            For coded: original string ID unchanged
        """
        ...

    def create_eval_set_run_payload(
        self,
        eval_set_id: str,
        agent_snapshot: StudioWebAgentSnapshot,
        no_of_evals: int,
        project_id: str,
    ) -> dict[str, Any]:
        """Create the payload for creating an eval set run."""
        ...

    def create_eval_run_payload(
        self,
        eval_item: EvaluationItem,
        eval_set_run_id: str,
    ) -> dict[str, Any]:
        """Create the payload for creating an eval run."""
        ...

    def create_update_eval_run_payload(
        self,
        eval_run_id: str,
        evaluator_runs: list[dict[str, Any]],
        evaluator_scores: list[dict[str, Any]],
        actual_output: dict[str, Any],
        execution_time: float,
        success: bool,
    ) -> dict[str, Any]:
        """Create the payload for updating an eval run."""
        ...

    def create_update_eval_set_run_payload(
        self,
        eval_set_run_id: str,
        evaluator_scores: dict[str, float],
        success: bool,
    ) -> dict[str, Any]:
        """Create the payload for updating an eval set run."""
        ...

    def collect_results(
        self,
        eval_results: list[Any],
        evaluators: dict[str, Any],
        usage_metrics: dict[str, int | float | None],
        serialize_justification_fn: Callable[[Any], str | None],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Collect results from evaluations in strategy-specific format.

        Returns:
            Tuple of (evaluator_runs, evaluator_scores)
        """
        ...
