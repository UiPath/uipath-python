"""Console progress reporter for evaluation runs using Rich UI components."""

import logging
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.text import Text

from uipath._cli._evals._models._evaluation_set import EvaluationItem, EvaluationStatus
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
from uipath.eval.models import EvalItemResult, ScoreType

logger = logging.getLogger(__name__)


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
            error_text = f" - {self.error_message}" if self.error_message else " - Failed"
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


    def start_display(self):
        """Start the display."""
        if not self.display_started:
            # Simple header with emoji and color
            self.console.print()
            self.console.print("🧪 [bold bright_blue]Running Evaluations[/bold bright_blue]")
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

            # Start the display on the first evaluation
            if not self.display_started:
                self.start_display()

            # Show the running evaluation with better formatting
            self.console.print(f"  ⏳ [dim]Starting[/dim] [bold white]{eval_item.name}[/bold white]...")
        except Exception as e:
            logger.error(f"Failed to handle create eval run event: {e}")

    async def handle_update_eval_run(self, payload: EvalRunUpdatedEvent) -> None:
        """Handle evaluation run updates."""
        try:
            eval_item = self.eval_items.get(payload.eval_item.id)
            if eval_item is None:
                logger.warning(f"Evaluation item {payload.eval_item.id} not found in display")
                return

            if payload.success:
                eval_item.status = "completed"
                # Calculate average score from all evaluator results
                if payload.eval_results:
                    total_score = 0.0
                    valid_scores = 0

                    for eval_result in payload.eval_results:
                        if eval_result.result.score_type == ScoreType.NUMERICAL:
                            total_score += eval_result.result.score
                            valid_scores += 1
                        elif eval_result.result.score_type == ScoreType.BOOLEAN:
                            total_score += 100 if eval_result.result.score else 0
                            valid_scores += 1

                    if valid_scores > 0:
                        eval_item.score = total_score / valid_scores

                # Show completion with score using better formatting
                if eval_item.score is not None:
                    if eval_item.score >= 90:
                        score_style = "bold green"
                        icon = "✅"
                    elif eval_item.score >= 70:
                        score_style = "bold yellow"
                        icon = "⚠️"
                    else:
                        score_style = "bold red"
                        icon = "❌"

                    self.console.print(f"  {icon} [bold white]{eval_item.name}[/bold white] [{score_style}]Score: {eval_item.score:.1f}[/{score_style}]")
                else:
                    self.console.print(f"  ✅ [bold white]{eval_item.name}[/bold white] [green]Completed[/green]")

                # Add a newline after each evaluation for better spacing
                self.console.print()
                self.completed_evaluations += 1
            else:
                eval_item.status = "failed"
                # Extract clean error message from the eval_item if available
                if hasattr(payload.eval_item, '_error_message'):
                    error_message = getattr(payload.eval_item, '_error_message', None)
                    if error_message:
                        error_msg = extract_clean_error_message(Exception(error_message), "Execution failed")
                    else:
                        error_msg = "Execution failed"
                else:
                    error_msg = "Execution failed"

                eval_item.error_message = error_msg
                self.console.print(f"  ❌ [bold white]{eval_item.name}[/bold white] [red]{error_msg}[/red]")
                # Add a newline after each evaluation for better spacing
                self.console.print()
                self.completed_evaluations += 1
        except Exception as e:
            logger.error(f"Failed to handle update eval run event: {e}")

    async def handle_update_eval_set_run(self, payload: EvalSetRunUpdatedEvent) -> None:
        """Handle evaluation set run completion."""
        try:
            # Calculate overall score
            if payload.evaluator_scores:
                total_score = sum(payload.evaluator_scores.values())
                self.overall_score = total_score / len(payload.evaluator_scores)

            self.console.print("")

            if self.overall_score is not None:
                if self.overall_score >= 80:
                    summary_style = "bold green"
                    summary_icon = "🎉"
                    summary_msg = "Excellent!"
                elif self.overall_score >= 60:
                    summary_style = "bold yellow"
                    summary_icon = "👍"
                    summary_msg = "Looks good!"
                else:
                    summary_style = "bold red"
                    summary_icon = "📈"
                    summary_msg = "Needs improvement."

                summary_text = Text(f"{summary_icon} {summary_msg} Final Score: {self.overall_score:.1f}/100", style=summary_style)
            else:
                summary_text = Text("🎯 All evaluations completed successfully!", style="bold green")

            self.console.print()
            self.console.print(summary_text)
            self.console.print()
        except Exception as e:
            logger.error(f"Failed to handle update eval set run event: {e}")

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