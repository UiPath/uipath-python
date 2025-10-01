"""Console progress reporter for evaluation runs using Rich UI components."""

import logging
from typing import Any, Dict, Optional

from rich.console import Console

from uipath._cli._evals._models._evaluation_set import EvaluationItem
from uipath._cli._utils._error_handling import extract_clean_error_message
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

EXCELLENT_THRESHOLD = 80
GOOD_THRESHOLD = 60


class EvalDisplayItem:
    """Represents a single evaluation item for display purposes."""

    def __init__(self, eval_item: EvaluationItem):
        self.id = eval_item.id
        self.name = eval_item.name
        self.status = "pending"  # pending, running, completed, failed
        self.score: Optional[float] = None
        self.error_message: Optional[str] = None

    def get_status_symbol(self) -> str:
        """Get the status symbol for this evaluation."""
        if self.status == "pending":
            return "⏳"
        elif self.status == "running":
            return "🔄"
        elif self.status == "completed":
            return "✅"
        elif self.status == "failed":
            return "❌"
        else:
            return "❓"

    def get_status_text(self) -> str:
        """Get status text for this evaluation."""
        symbol = self.get_status_symbol()

        if self.status == "pending":
            return f"{symbol} {self.name}"
        elif self.status == "running":
            return f"{symbol} {self.name}"
        elif self.status == "completed":
            score_text = f" - Score: {self.score:.1f}" if self.score is not None else ""
            return f"{symbol} {self.name}{score_text}"
        elif self.status == "failed":
            error_text = (
                f" - {self.error_message}" if self.error_message else " - Failed"
            )
            return f"{symbol} {self.name}{error_text}"
        else:
            return f"{symbol} {self.name}"


class ConsoleProgressReporter:
    """Handles displaying evaluation progress to the console using Rich."""

    def __init__(self):
        self.console = Console()
        self.eval_items: Dict[str, EvalDisplayItem] = {}
        self.evaluators: Dict[str, BaseEvaluator[Any]] = {}
        self.total_evaluations = 0
        self.completed_evaluations = 0
        self.overall_score: Optional[float] = None
        self.eval_set_name = "Evaluation Set"
        self.display_started = False

    def _format_error_message(self, error: Exception, context: str) -> None:
        """Helper method to format and display error messages consistently."""
        self.console.print(f"    • ⚠️  [dim]{context}: {error}[/dim]")

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

    def _display_successful_evaluation(
        self, eval_item: EvalDisplayItem, eval_results
    ) -> None:
        """Display results for a successful evaluation."""
        if eval_results:
            # Determine overall status icon based on worst individual score
            min_score = min(
                self._convert_score_to_numeric(eval_result)
                for eval_result in eval_results
            )
            icon = self._get_status_icon(min_score)

            self.console.print(f"  {icon} [bold white]{eval_item.name}[/bold white]")

            # Display individual evaluator scores
            for eval_result in eval_results:
                evaluator_name = self._get_evaluator_name(eval_result.evaluator_id)
                score_value = self._convert_score_to_numeric(eval_result)
                score_style = self._get_score_style(score_value)

                self.console.print(
                    f"    • [{score_style}]{evaluator_name}: {score_value:.1f}[/{score_style}]"
                )
        else:
            self.console.print(
                f"  ✅ [bold white]{eval_item.name}[/bold white] [green]Completed[/green]"
            )

    def _extract_error_message(self, eval_item_payload) -> str:
        """Extract clean error message from evaluation item."""
        if hasattr(eval_item_payload, "_error_message"):
            error_message = getattr(eval_item_payload, "_error_message", None)
            if error_message:
                return extract_clean_error_message(
                    Exception(error_message), "Execution failed"
                )
        return "Execution failed"

    def _display_failed_evaluation(
        self, eval_item: EvalDisplayItem, error_msg: str
    ) -> None:
        """Display results for a failed evaluation."""
        eval_item.error_message = error_msg
        self.console.print(
            f"  ❌ [bold white]{eval_item.name}[/bold white] [red]{error_msg}[/red]"
        )

    def _get_final_results_icon(self, score: float) -> str:
        """Get the appropriate icon for final results based on score."""
        if score >= EXCELLENT_THRESHOLD:
            return "🎉"
        elif score >= GOOD_THRESHOLD:
            return "👍"
        else:
            return "📈"

    def _get_score_style(self, score: float) -> str:
        """Get the appropriate style for a score based on thresholds."""
        if score >= EXCELLENT_THRESHOLD:
            return "bold green"
        elif score >= GOOD_THRESHOLD:
            return "bold yellow"
        else:
            return "bold red"

    def _get_status_icon(self, score: float) -> str:
        """Get the appropriate status icon for a score based on thresholds."""
        if score >= EXCELLENT_THRESHOLD:
            return "✅"
        elif score >= GOOD_THRESHOLD:
            return "⚠️"
        else:
            return "❌"

    def start_display(self):
        """Start the display."""
        if not self.display_started:
            self.console.print()
            self.console.print(
                "🧪 [bold bright_blue]Running Evaluations[/bold bright_blue]"
            )
            self.console.print()
            self.display_started = True

    async def handle_create_eval_set_run(self, payload: EvalSetRunCreatedEvent) -> None:
        """Handle evaluation set run creation."""
        try:
            self.evaluators = {eval.id: eval for eval in payload.evaluators}
            self.total_evaluations = payload.no_of_evals
            self.eval_set_name = "Evaluation Set"
        except Exception as e:
            logger.error(f"Failed to handle create eval set run event: {e}")

    async def handle_create_eval_run(self, payload: EvalRunCreatedEvent) -> None:
        """Handle individual evaluation run creation."""
        try:
            eval_item = EvalDisplayItem(payload.eval_item)
            eval_item.status = "running"
            self.eval_items[payload.eval_item.id] = eval_item

            if not self.display_started:
                self.start_display()

            self.console.print(
                f"  ⏳ [dim]Starting[/dim] [bold white]{eval_item.name}[/bold white]..."
            )
        except Exception as e:
            logger.error(f"Failed to handle create eval run event: {e}")

    async def handle_update_eval_run(self, payload: EvalRunUpdatedEvent) -> None:
        """Handle evaluation run updates."""
        try:
            eval_item = self.eval_items.get(payload.eval_item.id)
            if eval_item is None:
                logger.warning(
                    f"Evaluation item {payload.eval_item.id} not found in display"
                )
                return

            if payload.success:
                eval_item.status = "completed"
                self._display_successful_evaluation(eval_item, payload.eval_results)
            else:
                eval_item.status = "failed"
                error_msg = self._extract_error_message(payload.eval_item)
                self._display_failed_evaluation(eval_item, error_msg)

            self.console.print()
            self.completed_evaluations += 1
        except Exception as e:
            self._format_error_message(e, "Console reporter error")

    async def handle_update_eval_set_run(self, payload: EvalSetRunUpdatedEvent) -> None:
        """Handle evaluation set run completion."""
        try:
            self.console.print("")

            if payload.evaluator_scores:
                # Show per-evaluator averages
                self.console.print(
                    "🎯 [bold bright_blue]Final Results[/bold bright_blue]"
                )
                self.console.print()

                for evaluator_id, avg_score in payload.evaluator_scores.items():
                    evaluator_name = self._get_evaluator_name(evaluator_id)
                    score_style = self._get_score_style(avg_score)
                    icon = self._get_final_results_icon(avg_score)

                    self.console.print(
                        f"  {icon} [{score_style}]{evaluator_name}: {avg_score:.1f}/100[/{score_style}]"
                    )

                self.console.print()
            else:
                self.console.print(
                    "🎯 [bold green]All evaluations completed successfully![/bold green]"
                )
                self.console.print()
        except Exception as e:
            self._format_error_message(e, "Console reporter error")

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
