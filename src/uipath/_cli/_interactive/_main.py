"""Main interactive CLI for evaluations."""

from pathlib import Path
from typing import List, Optional, Tuple

from .._utils._console import ConsoleLogger
from ._discovery import DiscoveryMixin
from ._drill_down import DrillDownMixin
from ._eval_sets import EvalSetMixin
from ._evaluators import EvaluatorMixin
from ._execution import ExecutionMixin
from ._navigation import HAS_NAVIGATION, NavigationMixin

console = ConsoleLogger()


class InteractiveEvalCLI(
    NavigationMixin,
    DiscoveryMixin,
    EvalSetMixin,
    EvaluatorMixin,
    ExecutionMixin,
    DrillDownMixin,
):
    """Simple, fast, keyboard-driven evaluation CLI."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.eval_sets: List[Tuple[str, Path]] = []
        self.evaluators: List[Tuple[str, Path]] = []
        self.current_selection = 0
        self.menu_items = [
            "📋 List eval sets",
            "⚙️  List evaluators",
            "⚡ Quick run (auto-select)",
            "➕ Create eval set",
            "➕ Create evaluator",
            "🎯 Run specific combination",
        ]
        self._discover_files()

    def run(self) -> None:
        """Run the interactive CLI."""
        self._show_ascii_art()

        if not HAS_NAVIGATION:
            console.warning(
                "⚠️  Terminal navigation not available. Using fallback mode."
            )
            console.info("Consider using a standard terminal for better experience.\n")
            self._run_fallback_mode()
            return

        try:
            self._run_navigation_mode()
        except KeyboardInterrupt:
            console.info("\n👋 Goodbye!")

    def _run_navigation_mode(self) -> None:
        """Run with arrow key navigation."""
        while True:
            self._clear_screen()
            self._show_ascii_art()
            self._show_menu(self.current_selection, self.menu_items)

            key = self._get_key_input()

            if key == "up":
                self.current_selection = (self.current_selection - 1) % len(
                    self.menu_items
                )
            elif key == "down":
                self.current_selection = (self.current_selection + 1) % len(
                    self.menu_items
                )
            elif key in ["enter", " "]:
                self._execute_menu_item_with_navigation(self.current_selection)
            elif key.isdigit() and 1 <= int(key) <= 6:
                self._execute_menu_item_with_navigation(int(key) - 1)

    def _execute_menu_item_with_navigation(self, index: int) -> None:
        """Execute menu item with navigation support."""
        if index == 0:
            self._drill_down_eval_sets()
        elif index == 1:
            self._drill_down_evaluators()
        elif index == 2:
            self._quick_run_with_navigation()
        elif index == 3:
            self._create_eval_set_interactive()
        elif index == 4:
            self._create_evaluator_interactive()
        elif index == 5:
            self._run_specific_combination()

    def _run_fallback_mode(self) -> None:
        """Run without navigation - simple text interface."""
        while True:
            console.info("\n⚙️  Main Menu:")
            for i, item in enumerate(self.menu_items, 1):
                console.info(f"  {i}. {item}")
            console.info("  0. Exit")

            try:
                choice = input("\n➤ Select option: ").strip()

                if choice == "0":
                    console.info("👋 Goodbye!")
                    break
                elif choice == "1":
                    self._list_eval_sets_navigation()
                elif choice == "2":
                    self._list_evaluators()
                elif choice == "3":
                    self._quick_run()
                elif choice == "4":
                    self._create_eval_set_simple()
                elif choice == "5":
                    self._create_evaluator_simple()
                elif choice == "6":
                    self._run_specific_combination()
                else:
                    console.warning("Invalid option")
            except KeyboardInterrupt:
                console.info("\n👋 Goodbye!")
                break

    def _quick_run_with_navigation(self) -> None:
        """Quick run evaluation with auto-selected eval set."""
        if not self.eval_sets:
            self._clear_screen()
            console.warning("No eval sets found!")
            console.info("Press Enter to go back...")
            self._get_input("")
            return

        # Use first eval set
        eval_name, eval_path = self.eval_sets[0]

        self._clear_screen()
        console.info(f"⚡ Quick Run: {eval_name}")
        console.info("─" * 65)

        if self._confirm("Run evaluation now?"):
            self._execute_evaluation_no_clear(eval_path)

    def _quick_run(self) -> None:
        """Quick run evaluation with auto-selected eval set."""
        if not self.eval_sets:
            console.warning("No eval sets found!")
            return

        # Use first eval set
        eval_name, eval_path = self.eval_sets[0]
        console.info(f"\n⚡ Quick Run: {eval_name}")

        if self._confirm("Run evaluation now?"):
            self._execute_evaluation(eval_path)

    def _list_eval_sets_navigation(self) -> None:
        """List eval sets with navigation."""
        self._clear_screen()
        console.info("📋 Available Eval Sets")
        console.info("─" * 65)
        self._list_eval_sets()
        input("\nPress Enter to continue...")

    def _run_specific_combination(self) -> None:
        """Run specific eval set and evaluator combination."""
        self._clear_screen()
        console.info("🎯 Run Specific Combination")
        console.info("─" * 65)

        # Select eval set
        console.info("\n📋 Select Eval Set:")
        for i, (name, _) in enumerate(self.eval_sets, 1):
            console.info(f"  {i}. {name}")

        try:
            eval_idx = int(input("\n➤ Eval Set Number: ").strip()) - 1
            if not (0 <= eval_idx < len(self.eval_sets)):
                console.error("Invalid selection")
                input("\nPress Enter to continue...")
                return

            eval_name, eval_path = self.eval_sets[eval_idx]

            console.info(f"\n✅ Selected: {eval_name}")
            if self._confirm("Run evaluation now?"):
                self._execute_evaluation_no_clear(eval_path)
        except ValueError:
            console.error("Invalid selection")
            input("\nPress Enter to continue...")


def launch_interactive_cli(project_root: Optional[Path] = None) -> None:
    """Launch the interactive CLI."""
    cli = InteractiveEvalCLI(project_root)
    cli.run()
