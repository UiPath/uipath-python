"""Drill-down navigation for eval sets and evaluators."""
# type: ignore

from typing import TYPE_CHECKING

from .._utils._console import ConsoleLogger

if TYPE_CHECKING:
    from ._main import InteractiveEvalCLI

console = ConsoleLogger()


class DrillDownMixin:
    """Mixin for drill-down navigation operations."""

    def _drill_down_eval_sets(self: "InteractiveEvalCLI") -> None:
        """Drill down into eval sets with navigation."""
        if not self.eval_sets:
            self._show_no_items_screen("eval sets")
            return

        current_selection = 0
        while True:
            self._clear_screen()
            console.info("📋 Eval Sets - Navigate & Select")
            console.info("⌨️  Navigation: ↑↓ to navigate, Enter for details, q/Backspace to go back")
            console.info("─" * 65)

            for i, (name, path) in enumerate(self.eval_sets):
                if i == current_selection:
                    console.info(f"► {i+1}. {name} ◄")
                    self._show_eval_set_preview(path)
                else:
                    console.info(f"  {i+1}. {name}")

            key = self._get_key_input()

            if key in ['q', 'Q', 'back']:
                break
            elif key == 'up':
                current_selection = (current_selection - 1) % len(self.eval_sets)
            elif key == 'down':
                current_selection = (current_selection + 1) % len(self.eval_sets)
            elif key in ['enter', ' ']:
                self._show_eval_set_details(self.eval_sets[current_selection])
            elif key.isdigit() and 1 <= int(key) <= len(self.eval_sets):
                current_selection = int(key) - 1

    def _drill_down_evaluators(self: "InteractiveEvalCLI") -> None:
        """Drill down into evaluators with navigation."""
        if not self.evaluators:
            self._show_no_items_screen("evaluators")
            return

        current_selection = 0
        while True:
            self._clear_screen()
            console.info("⚙️  Evaluators - Navigate & Select")
            console.info("⌨️  Navigation: ↑↓ to navigate, Enter for details, q/Backspace to go back")
            console.info("─" * 65)

            for i, (name, path) in enumerate(self.evaluators):
                if i == current_selection:
                    console.info(f"► {i+1}. {name} ◄")
                    self._show_evaluator_preview(path)
                else:
                    console.info(f"  {i+1}. {name}")

            key = self._get_key_input()

            if key in ['q', 'Q', 'back']:
                break
            elif key == 'up':
                current_selection = (current_selection - 1) % len(self.evaluators)
            elif key == 'down':
                current_selection = (current_selection + 1) % len(self.evaluators)
            elif key in ['enter', ' ']:
                self._show_evaluator_details(self.evaluators[current_selection])
            elif key.isdigit() and 1 <= int(key) <= len(self.evaluators):
                current_selection = int(key) - 1

    def _show_no_items_screen(self: "InteractiveEvalCLI", item_type: str) -> None:
        """Show no items screen."""
        self._clear_screen()
        console.warning(f"No {item_type} found!")
        console.info("Press Enter to go back...")
        self._get_input("")
