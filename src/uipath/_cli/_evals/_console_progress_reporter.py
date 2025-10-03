"""Console progress reporter for evaluation runs with line-by-line output."""

import logging
from typing import Any, Dict

from rich.console import Console

from uipath._events._event_bus import EventBus
from uipath._events._events import (
    EvalRunCreatedEvent,
    EvalRunUpdatedEvent,
    EvalSetRunCreatedEvent,
    EvalSetRunUpdatedEvent,
    EvaluationEvents,
)
from uipath.eval.evaluators import BaseEvaluator
from uipath.eval.models import ScoreType

logger = logging.getLogger(__name__)


class ConsoleProgressReporter:
    """Handles displaying evaluation progress to the console with line-by-line output."""

    def __init__(self):
        self.console = Console()
        self.evaluators: Dict[str, BaseEvaluator[Any]] = {}
        self.display_started = False

    def _convert_score_to_numeric(self, eval_result) -> float:
        """Convert evaluation result score to numeric value."""
        score_value = eval_result.result.score
        if eval_result.result.score_type == ScoreType.BOOLEAN:
            score_value = 100 if score_value else 0
        return score_value

    def _get_evaluator_name(self, evaluator_id: str) -> str:
        """Get evaluator name from ID, with fallback."""
        return self.evaluators.get(
            evaluator_id,
            type(
                "obj",
                (object,),
                {"name": f"Evaluator {evaluator_id[:8]}"},
            )(),
        ).name

    def _display_successful_evaluation(self, eval_name: str, eval_results) -> None:
        """Display results for a successful evaluation."""
        if eval_results:
            # Create details string with evaluator scores
            details_parts = []
            for eval_result in eval_results:
                evaluator_name = self._get_evaluator_name(eval_result.evaluator_id)
                score_value = self._convert_score_to_numeric(eval_result)
                details_parts.append(f"{evaluator_name}: {score_value:.1f}")

            details = " | ".join(details_parts)
            self.console.print(f"  ✓ [green]{eval_name}[/green] - {details}")
        else:
            self.console.print(f"  ✓ [green]{eval_name}[/green] - No evaluators")

    def _extract_error_message(self, eval_item_payload) -> str:
        """Extract clean error message from evaluation item."""
        if hasattr(eval_item_payload, "_error_message"):
            error_message = getattr(eval_item_payload, "_error_message", None)
            if error_message:
                return str(error_message) or "Execution failed"
        return "Execution failed"

    def _display_failed_evaluation(self, eval_name: str, error_msg: str) -> None:
        """Display results for a failed evaluation."""
        self.console.print(f"  ✗ [red]{eval_name}[/red] - {error_msg}")

    def start_display(self):
        """Start the display."""
        if not self.display_started:
            self.console.print()
            self.console.print("→ [bold]Running Evaluations[/bold]")
            self.console.print()
            self.display_started = True

    async def handle_create_eval_set_run(self, payload: EvalSetRunCreatedEvent) -> None:
        """Handle evaluation set run creation."""
        try:
            self.evaluators = {eval.id: eval for eval in payload.evaluators}
        except Exception as e:
            logger.error(f"Failed to handle create eval set run event: {e}")

    async def handle_create_eval_run(self, payload: EvalRunCreatedEvent) -> None:
        """Handle individual evaluation run creation."""
        try:
            if not self.display_started:
                self.start_display()

            self.console.print(f"  ○ [dim]{payload.eval_item.name}[/dim] - Running...")
        except Exception as e:
            logger.error(f"Failed to handle create eval run event: {e}")

    async def handle_update_eval_run(self, payload: EvalRunUpdatedEvent) -> None:
        """Handle evaluation run updates."""
        try:
            if payload.success:
                self._display_successful_evaluation(
                    payload.eval_item.name, payload.eval_results
                )
            else:
                error_msg = self._extract_error_message(payload.eval_item)
                self._display_failed_evaluation(payload.eval_item.name, error_msg)
        except Exception as e:
            logger.error(f"Console reporter error: {e}")

    async def handle_update_eval_set_run(self, payload: EvalSetRunUpdatedEvent) -> None:
        """Handle evaluation set run completion."""
        try:
            self.final_results = payload.evaluator_scores
        except Exception as e:
            logger.error(f"Console reporter error: {e}")

    def display_final_results(self):
        """Display final results summary."""
        self.console.print()

        if hasattr(self, "final_results") and self.final_results:
            # Show per-evaluator averages in a table
            from rich.table import Table

            results_summary_table = Table(title="Final Results")
            results_summary_table.add_column("Evaluator", style="bold")
            results_summary_table.add_column("Average Score", justify="right")

            for evaluator_id, avg_score in self.final_results.items():
                evaluator_name = self._get_evaluator_name(evaluator_id)
                results_summary_table.add_row(evaluator_name, f"{avg_score:.1f}/100")

            self.console.print(results_summary_table)
            self.console.print()
        else:
            self.console.print(
                "→ [bold green]All evaluations completed successfully![/bold green]"
            )
            self.console.print()

    async def subscribe_to_eval_runtime_events(self, event_bus: EventBus) -> None:
        """Subscribe to evaluation runtime events."""
        event_bus.subscribe(
            EvaluationEvents.CREATE_EVAL_SET_RUN, self.handle_create_eval_set_run
        )
        event_bus.subscribe(
            EvaluationEvents.CREATE_EVAL_RUN, self.handle_create_eval_run
        )
        event_bus.subscribe(
            EvaluationEvents.UPDATE_EVAL_RUN, self.handle_update_eval_run
        )
        event_bus.subscribe(
            EvaluationEvents.UPDATE_EVAL_SET_RUN, self.handle_update_eval_set_run
        )
