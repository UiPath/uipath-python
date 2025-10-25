"""Console progress reporter for evaluation runs with line-by-line output."""

import logging
from typing import Any, Dict

from rich.console import Console
from rich.rule import Rule
from rich.table import Table

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
        self.evaluators: Dict[str, BaseEvaluator[Any, Any, Any]] = {}
        self.display_started = False
        self.eval_results_by_name: Dict[str, list[Any]] = {}

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

    def _extract_error_message(self, payload: EvalRunUpdatedEvent) -> str:
        return str(payload.exception_details.exception) or "Execution failed"  # type: ignore

    def _display_failed_evaluation(self, eval_name: str) -> None:
        """Display results for a failed evaluation."""
        from rich.text import Text

        result = Text()
        result.append("  ✗ ", style="bold red")
        result.append(eval_name, style="bold white")
        self.console.print(result)

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

    def _display_logs_panel(self, eval_name: str, logs, error_msg: str = "") -> None:
        """Display execution logs panel with optional exception at the end."""
        self.console.print(
            Rule(
                f"[dim italic]Execution Logs: {eval_name}[/dim italic]",
                style="dim",
                align="center",
            )
        )

        if logs:
            for record in logs:
                self.console.print(f"  [dim]{record.getMessage()}[/dim]")
        elif not error_msg:
            self.console.print("  [dim italic]No execution logs[/dim italic]")

        if error_msg:
            self.console.print(f"  [red]{error_msg}[/red]")

        self.console.print(Rule(style="dim"))

    async def handle_update_eval_run(self, payload: EvalRunUpdatedEvent) -> None:
        """Handle evaluation run updates."""
        try:
            if payload.success:
                self.eval_results_by_name[payload.eval_item.name] = payload.eval_results
                self._display_successful_evaluation(
                    payload.eval_item.name, payload.eval_results
                )
                self._display_logs_panel(payload.eval_item.name, payload.logs)
            else:
                error_msg = self._extract_error_message(payload)
                self._display_failed_evaluation(payload.eval_item.name)

                if payload.exception_details.runtime_exception:  # type: ignore
                    self._display_logs_panel(
                        payload.eval_item.name, payload.logs, error_msg
                    )
                else:
                    self.console.print(f"  [red]{error_msg}[/red]")
                    self.console.print()
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
