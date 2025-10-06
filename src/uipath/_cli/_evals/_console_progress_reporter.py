"""Console progress reporter for evaluation runs with line-by-line output."""

import logging
import os
import time
from typing import Any, Dict, Optional

from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from uipath._events._event_bus import EventBus
from uipath._events._events import (
    BatchProgressEvent,
    EvalProgressEvent,
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
        self.eval_results_by_name: Dict[str, list[Any]] = {}
        self.total_batches = 0
        self.completed_batches = 0
        self.is_parallel_execution = False

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
        from rich.text import Text

        if eval_results:
            result = Text()
            result.append("▌", style="bold green")
            result.append(" ", style="")
            result.append(eval_name, style="bold green")
            self.console.print(result)
            table = Table(show_header=False, box=None, padding=(0, 2, 0, 2))

            for eval_result in eval_results:
                evaluator_name = self._get_evaluator_name(eval_result.evaluator_id)
                score_value = self._convert_score_to_numeric(eval_result)
                table.add_row(
                    f"{evaluator_name}", f"[bold cyan]{score_value:.1f}[/bold cyan]"
                )

            self.console.print(table)
        else:
            result = Text()
            result.append("  ✓ ", style="bold green")
            result.append(eval_name, style="bold white")
            result.append(" - No evaluators", style="dim")
            self.console.print(result)

    def _extract_error_message(self, eval_item_payload) -> str:
        """Extract clean error message from evaluation item."""
        if hasattr(eval_item_payload, "_error_message"):
            error_message = getattr(eval_item_payload, "_error_message", None)
            if error_message:
                return str(error_message) or "Execution failed"
        return "Execution failed"

    def _display_failed_evaluation(self, eval_name: str, error_msg: str) -> None:
        """Display results for a failed evaluation."""
        from rich.text import Text

        result = Text()
        result.append("  ✗ ", style="bold red")
        result.append(eval_name, style="bold white")
        self.console.print(result)

        error_text = Text()
        error_text.append("    ", style="")
        error_text.append(error_msg, style="red")
        self.console.print(error_text)

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
                # Store results for final display
                self.eval_results_by_name[payload.eval_item.name] = payload.eval_results
                self._display_successful_evaluation(
                    payload.eval_item.name, payload.eval_results
                )
            else:
                error_msg = self._extract_error_message(payload.eval_item)
                self._display_failed_evaluation(payload.eval_item.name, error_msg)

            logs = payload.logs

            self.console.print(
                Rule(
                    f"[dim italic]Execution Logs: {payload.eval_item.name}[/dim italic]",
                    style="dim",
                    align="center",
                )
            )

            if len(logs) > 0:
                for record in logs:
                    log_line = f"  [dim]{record.getMessage()}[/dim]"
                    self.console.print(log_line)
            else:
                self.console.print("  [dim italic]No execution logs[/dim italic]")

            self.console.print(Rule(style="dim"))
        except Exception as e:
            logger.error(f"Console reporter error: {e}")

    async def handle_update_eval_set_run(self, payload: EvalSetRunUpdatedEvent) -> None:
        """Handle evaluation set run completion."""
        try:
            self.final_results = payload.evaluator_scores
            self.display_final_results()
        except Exception as e:
            logger.error(f"Console reporter error: {e}")

    def display_final_results(self):
        """Display final results summary."""
        self.console.print()

        if hasattr(self, "final_results") and self.final_results:
            from rich.table import Table

            # Group evaluators by ID to organize display
            evaluator_ids = list(self.final_results.keys())

            # Print title
            self.console.print("[bold]Evaluation Results[/bold]")
            self.console.print()

            # Create single summary table
            summary_table = Table(show_header=True, padding=(0, 2))
            summary_table.add_column("Evaluation", style="cyan")

            # Add column for each evaluator
            for evaluator_id in evaluator_ids:
                evaluator_name = self._get_evaluator_name(evaluator_id)
                summary_table.add_column(evaluator_name, justify="right")

            # Add row for each evaluation
            for eval_name, eval_results in self.eval_results_by_name.items():
                row_values = [eval_name]

                # Get score for each evaluator
                for evaluator_id in evaluator_ids:
                    score_found = False
                    for eval_result in eval_results:
                        if eval_result.evaluator_id == evaluator_id:
                            score_value = self._convert_score_to_numeric(eval_result)
                            row_values.append(f"{score_value:.1f}")
                            score_found = True
                            break

                    if not score_found:
                        row_values.append("-")

                summary_table.add_row(*row_values)

            # Add separator row before average
            summary_table.add_section()

            # Add average row
            avg_row_values = ["[bold]Average[/bold]"]
            for evaluator_id in evaluator_ids:
                avg_score = self.final_results[evaluator_id]
                avg_row_values.append(f"[bold]{avg_score:.1f}[/bold]")

            summary_table.add_row(*avg_row_values)

            self.console.print(summary_table)
            self.console.print()
        else:
            self.console.print(
                "→ [bold green]All evaluations completed successfully![/bold green]"
            )
            self.console.print()

    async def handle_eval_progress(self, payload: EvalProgressEvent) -> None:
        """Handle evaluation progress updates."""
        try:
            if self.is_parallel_execution:
                progress_bar = self._create_progress_bar(
                    payload.completed_evals, payload.total_evals, "evaluations"
                )
                self.console.print(f"\r  📊 {progress_bar}", end="")
        except Exception as e:
            logger.error(f"Failed to handle eval progress event: {e}")

    async def handle_batch_progress(self, payload: BatchProgressEvent) -> None:
        """Handle batch progress updates."""
        try:
            if payload.completed_batches == 1:
                self.is_parallel_execution = True
                self.total_batches = payload.total_batches
                self.console.print()
                self.console.print(
                    f"  🔄 [bold bright_blue]Running {payload.total_batches} batches in parallel...[/bold bright_blue]"
                )

            self.completed_batches = payload.completed_batches

            if self.total_batches > 1:
                batch_progress = self._create_progress_bar(
                    payload.completed_batches, payload.total_batches, "batches"
                )
                self.console.print(f"  📦 {batch_progress}")

        except Exception as e:
            logger.error(f"Failed to handle batch progress event: {e}")

    def _create_progress_bar(self, completed: int, total: int, unit: str) -> str:
        """Create a simple text progress bar."""
        if total == 0:
            return f"[dim]{unit}: 0/0[/dim]"

        percentage = (completed / total) * 100
        filled = int(percentage / 10)  # 10 segments
        bar = "█" * filled + "░" * (10 - filled)

        return f"[bright_blue]{bar}[/bright_blue] {completed}/{total} {unit} ([bold]{percentage:.1f}%[/bold])"

    def _display_total_duration(self) -> None:
        """Display the total evaluation duration."""
        try:
            start_time_str = os.environ.get("UIPATH_EVAL_START_TIME")
            if start_time_str:
                start_time = float(start_time_str)
                end_time = time.time()
                duration = end_time - start_time

                if duration < 60:
                    duration_str = f"{duration:.1f}s"
                else:
                    minutes = int(duration // 60)
                    seconds = duration % 60
                    duration_str = f"{minutes}m {seconds:.1f}s"

                self.console.print(f"⏱️  [dim]Total time: {duration_str}[/dim]")
                self.console.print()
        except Exception:
            pass

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
        event_bus.subscribe(EvaluationEvents.EVAL_PROGRESS, self.handle_eval_progress)
        event_bus.subscribe(EvaluationEvents.BATCH_PROGRESS, self.handle_batch_progress)
