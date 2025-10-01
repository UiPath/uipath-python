"""Simple interactive CLI for evaluations - keyboard only, no mouse."""

import json
import subprocess
import sys
import termios
import tty
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ._utils._console import ConsoleLogger


def has_termios() -> bool:
    """Check if we have termios support for advanced input."""
    try:
        termios.tcgetattr(sys.stdin)
        return True
    except Exception:
        return False


HAS_NAVIGATION = has_termios()
console = ConsoleLogger()


class InteractiveEvalCLI:
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
            "🎯 Run specific combination"
        ]
        self._discover_files()

    def _show_ascii_art(self):
        """Display ASCII art banner."""
        art = """
  ██╗   ██╗██╗██████╗  █████╗ ████████╗██╗  ██╗
  ██║   ██║██║██╔══██╗██╔══██╗╚══██╔══╝██║  ██║
  ██║   ██║██║██████╔╝███████║   ██║   ███████║
  ██║   ██║██║██╔═══╝ ██╔══██║   ██║   ██╔══██║
  ╚██████╔╝██║██║     ██║  ██║   ██║   ██║  ██║
   ╚═════╝ ╚═╝╚═╝     ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝

            Evaluation Builder
        Interactive Evaluation Toolkit
        """
        console.info(art)

    def _discover_files(self) -> None:
        """Quickly discover eval sets and evaluators."""
        # Clear existing lists to avoid duplicates
        self.eval_sets.clear()
        self.evaluators.clear()

        # Find eval sets from evaluationSets folder
        eval_sets_dir = self.project_root / "evaluationSets"
        if eval_sets_dir.exists():
            for eval_file in eval_sets_dir.glob("*.json"):
                try:
                    with open(eval_file) as f:
                        data = json.load(f)
                    # Check if it's an eval set by presence of "evaluations" array
                    if "evaluations" in data and isinstance(data.get("evaluations"), list):
                        name = data.get("name", eval_file.stem)
                        self.eval_sets.append((name, eval_file))
                except Exception:
                    pass

        # Find evaluators from evaluators folder
        evaluators_dir = self.project_root / "evaluators"
        if evaluators_dir.exists():
            for eval_file in evaluators_dir.glob("*.json"):
                try:
                    with open(eval_file) as f:
                        data = json.load(f)
                    # Verify it has evaluator-specific fields
                    if "id" in data and "type" in data:
                        name = data.get("name", eval_file.stem)
                        self.evaluators.append((name, eval_file))
                except Exception:
                    pass

    def run(self) -> None:
        """Run the interactive CLI."""
        self._show_ascii_art()

        if HAS_NAVIGATION:
            self._run_with_navigation()
        else:
            self._run_basic()

    def _run_with_navigation(self) -> None:
        """Run with arrow key navigation."""
        while True:
            try:
                self._clear_screen()
                self._show_status()
                self._show_navigable_menu()

                # Get key input
                key = self._get_key_input()

                if key in ['q', 'Q']:
                    console.info("👋 Goodbye!")
                    break
                elif key == 'up':
                    self.current_selection = (self.current_selection - 1) % len(self.menu_items)
                elif key == 'down':
                    self.current_selection = (self.current_selection + 1) % len(self.menu_items)
                elif key in ['enter', ' ']:
                    self._execute_menu_item_with_navigation(self.current_selection)
                elif key.isdigit() and 1 <= int(key) <= len(self.menu_items):
                    self.current_selection = int(key) - 1
                    self._execute_menu_item_with_navigation(self.current_selection)

            except KeyboardInterrupt:
                console.info("\n👋 Goodbye!")
                break
            except Exception as e:
                console.error(f"Error: {e}")
                self._get_input("\nPress Enter to continue...")

    def _run_basic(self) -> None:
        """Run basic mode without arrow keys."""
        while True:
            try:
                self._show_status()
                self._show_main_menu()
                choice = self._get_input("\nChoice (1-6, q to quit): ").strip().lower()

                if choice == 'q':
                    console.info("👋 Goodbye!")
                    break
                elif choice.isdigit() and 1 <= int(choice) <= len(self.menu_items):
                    self._execute_menu_item(int(choice) - 1)
                else:
                    console.warning("Invalid choice. Try again.")

                if choice in ['1', '2']:
                    self._get_input("\nPress Enter to continue...")

            except KeyboardInterrupt:
                console.info("\n👋 Goodbye!")
                break
            except Exception as e:
                console.error(f"Error: {e}")

    def _clear_screen(self) -> None:
        """Clear the screen."""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
        self._show_ascii_art()

    def _show_status(self) -> None:
        """Show project status."""
        console.info(f"📁 Project: {self.project_root.name}")
        console.info(f"📋 Eval Sets: {len(self.eval_sets)} | ⚙️  Evaluators: {len(self.evaluators)}")
        console.info("─" * 65)

    def _show_navigable_menu(self) -> None:
        """Show menu with current selection highlighted."""
        console.info("\n⌨️  Navigation: ↑↓ to navigate, Enter/Space to select, 1-6 for direct, q to quit, Backspace to go back")
        console.info("─" * 65)

        for i, item in enumerate(self.menu_items):
            if i == self.current_selection:
                console.info(f"► {i+1}. {item} ◄")
            else:
                console.info(f"  {i+1}. {item}")

    def _get_key_input(self) -> str:
        """Get key input with arrow key support."""
        if not HAS_NAVIGATION:
            return input("➤ ").strip().lower()

        try:
            # Set terminal to raw mode
            old_settings = termios.tcgetattr(sys.stdin)
            tty.setraw(sys.stdin)

            char = sys.stdin.read(1)

            # Handle escape sequences (arrow keys)
            if char == '\x1b':  # ESC
                char += sys.stdin.read(2)
                if char == '\x1b[A':  # Up arrow
                    return 'up'
                elif char == '\x1b[B':  # Down arrow
                    return 'down'
                elif char == '\x1b[C':  # Right arrow
                    return 'enter'
                elif char == '\x1b[D':  # Left arrow
                    return 'up'
            elif char == '\r' or char == '\n':  # Enter
                return 'enter'
            elif char == ' ':  # Space
                return 'enter'
            elif char in ['q', 'Q']:
                return 'q'
            elif char == '\x7f':  # Backspace (DEL)
                return 'back'
            elif char == '\x08':  # Backspace (BS)
                return 'back'
            elif char.isdigit() and 1 <= int(char) <= 6:
                return char
            elif char == '\x03':  # Ctrl+C
                raise KeyboardInterrupt

            return ''
        except Exception:
            return input("➤ ").strip().lower()
        finally:
            # Restore terminal settings
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            except Exception:
                pass

    def _execute_menu_item_with_navigation(self, index: int) -> None:
        """Execute menu item with navigation support."""
        if index == 0:
            self._drill_down_eval_sets()
        elif index == 1:
            self._drill_down_evaluators()
        elif index == 2:
            self._quick_run_no_clear()
        elif index == 3:
            self._create_eval_set_interactive()
        elif index == 4:
            self._create_evaluator_interactive()
        elif index == 5:
            self._run_specific_navigation()

    def _execute_menu_item(self, index: int) -> None:
        """Execute selected menu item (basic mode)."""
        if index == 0:
            self._list_eval_sets()
        elif index == 1:
            self._list_evaluators()
        elif index == 2:
            self._quick_run()
        elif index == 3:
            self._create_eval_set()
        elif index == 4:
            self._create_evaluator()
        elif index == 5:
            self._run_specific()

        if index in [0, 1]:
            self._get_input("\nPress Enter to continue...")

    def _show_main_menu(self) -> None:
        """Show main menu options."""
        console.info(f"\n📁 Project: {self.project_root.name}")
        console.info(f"📋 Eval Sets: {len(self.eval_sets)} | ⚙️  Evaluators: {len(self.evaluators)}")
        console.info("\n" + "─" * 50)
        console.info("1. 📋 List eval sets")
        console.info("2. ⚙️  List evaluators")
        console.info("3. ⚡ Quick run (auto-select)")
        console.info("4. ➕ Create eval set")
        console.info("5. ➕ Create evaluator")
        console.info("6. 🎯 Run specific combination")

    def _list_eval_sets(self) -> None:
        """List available evaluation sets."""
        console.info("\n📋 Available Eval Sets:")
        if not self.eval_sets:
            console.warning("No eval sets found")
            return

        for i, (name, path) in enumerate(self.eval_sets, 1):
            # Load test count
            try:
                with open(path) as f:
                    data = json.load(f)
                test_count = len(data.get("evaluations", []))
                evaluator_count = len(data.get("evaluatorRefs", []))
                console.info(f"{i}. {name}")
                console.info(f"   Tests: {test_count} | Evaluators: {evaluator_count}")
                console.info(f"   File: {path.name}")
            except Exception:
                console.info(f"{i}. {name} (error loading)")

    def _list_evaluators(self) -> None:
        """List available evaluators."""
        console.info("\n⚙️  Available Evaluators:")
        if not self.evaluators:
            console.warning("No evaluators found")
            return

        for i, (name, path) in enumerate(self.evaluators, 1):
            try:
                with open(path) as f:
                    data = json.load(f)
                category = self._get_category_name(data.get("category", 0))
                type_name = self._get_type_name(data.get("type", 1))
                console.info(f"{i}. {name}")
                console.info(f"   Type: {category} | {type_name}")
                console.info(f"   File: {path.name}")
            except Exception:
                console.info(f"{i}. {name} (error loading)")

    def _list_eval_sets_navigation(self) -> None:
        """List eval sets with navigation."""
        self._clear_screen()
        console.info("📋 Available Eval Sets")
        console.info("─" * 65)
        self._list_eval_sets()
        console.info("\n⌨️  Press any key to go back...")
        self._get_key_input()

    def _list_evaluators_navigation(self) -> None:
        """List evaluators with navigation."""
        self._clear_screen()
        console.info("⚙️  Available Evaluators")
        console.info("─" * 65)
        self._list_evaluators()
        console.info("\n⌨️  Press any key to go back...")
        self._get_key_input()

    def _quick_run(self) -> None:
        """Quick run with auto-selection."""
        if not self.eval_sets:
            console.error("No eval sets found!")
            return

        if not self.evaluators:
            console.error("No evaluators found!")
            return

        console.info("\n⚡ Quick Run:")

        # Auto-select first eval set
        eval_name, eval_path = self.eval_sets[0]
        console.info(f"📋 Using eval set: {eval_name}")

        # Auto-select all evaluators
        console.info(f"⚙️  Using {len(self.evaluators)} evaluators")

        if self._confirm("Run evaluation now?"):
            self._execute_evaluation(eval_path)

    def _quick_run_no_clear(self) -> None:
        """Quick run without clearing screen."""
        if not self.eval_sets:
            console.error("No eval sets found!")
            input("\nPress Enter to continue...")
            return

        if not self.evaluators:
            console.error("No evaluators found!")
            input("\nPress Enter to continue...")
            return

        console.info("\n⚡ Quick Run:")

        # Auto-select first eval set
        eval_name, eval_path = self.eval_sets[0]
        console.info(f"📋 Using eval set: {eval_name}")

        # Auto-select all evaluators
        console.info(f"⚙️  Using {len(self.evaluators)} evaluators")

        if self._confirm("Run evaluation now?"):
            self._execute_evaluation_no_clear(eval_path)

    def _run_specific(self) -> None:
        """Run with specific selection."""
        if not self.eval_sets or not self.evaluators:
            console.error("Need both eval sets and evaluators!")
            return

        # Select eval set with navigation
        eval_choice = self._select_from_list(self.eval_sets, "Eval Set")
        if eval_choice is None:
            return

        eval_name, eval_path = self.eval_sets[eval_choice - 1]
        console.success(f"Selected: {eval_name}")

        # Confirm and run
        if self._confirm("Run evaluation now?"):
            self._execute_evaluation(eval_path)

    def _run_specific_navigation(self) -> None:
        """Run specific combination with navigation."""
        if not self.eval_sets or not self.evaluators:
            console.error("Need both eval sets and evaluators!")
            input("\nPress Enter to continue...")
            return

        # Select eval set
        self._clear_screen()
        console.info("🎯 Select Evaluation Set")
        console.info("─" * 65)
        self._list_eval_sets()

        choice = input("\n➤ Select eval set number (or q to cancel): ").strip()
        if choice.lower() == 'q':
            return

        try:
            eval_choice = int(choice)
            if 1 <= eval_choice <= len(self.eval_sets):
                eval_name, eval_path = self.eval_sets[eval_choice - 1]
                console.success(f"Selected: {eval_name}")

                if self._confirm("Run evaluation now?"):
                    self._execute_evaluation_no_clear(eval_path)
        except ValueError:
            console.error("Invalid selection")
            input("\nPress Enter to continue...")

    def _execute_evaluation(self, eval_path: Path) -> None:
        """Execute evaluation with live results."""
        console.info("\n🚀 Running evaluation...")

        # Find main.py
        main_py = self._find_main_py()
        if not main_py:
            console.error("Could not find main.py")
            return

        # Build command - run from the project directory
        cmd = [
            sys.executable, "-m", "uipath._cli.cli_eval",
            str(main_py.relative_to(self.project_root)),
            str(eval_path.relative_to(self.project_root)),
            "--no-report", "--workers", "1"
        ]

        console.info(f"💻 Command: uipath eval {main_py.name} {eval_path.name} --no-report")

        try:
            # Run with real-time output from project directory
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=self.project_root
            )

            # Stream output in real-time
            if process.stdout:
                for line in process.stdout:
                    print(line.rstrip())

            process.wait()

            if process.returncode == 0:
                console.success("\n✅ Evaluation completed successfully!")
            else:
                console.error(f"\n❌ Evaluation failed (exit code: {process.returncode})")

        except Exception as e:
            console.error(f"Failed to run evaluation: {e}")

    def _execute_evaluation_no_clear(self, eval_path: Path) -> None:
        """Execute evaluation without clearing screen."""
        console.info("\n🚀 Running evaluation...")

        # Find main.py
        main_py = self._find_main_py()
        if not main_py:
            console.error("Could not find main.py")
            input("\nPress Enter to continue...")
            return

        # Build command - run from the project directory
        cmd = [
            sys.executable, "-m", "uipath._cli.cli_eval",
            str(main_py.relative_to(self.project_root)),
            str(eval_path.relative_to(self.project_root)),
            "--no-report", "--workers", "1"
        ]

        console.info(f"💻 Command: uipath eval {main_py.name} {eval_path.name} --no-report")

        try:
            # Run with real-time output from project directory
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=self.project_root
            )

            # Stream output in real-time
            if process.stdout:
                for line in process.stdout:
                    print(line.rstrip())

            process.wait()

            if process.returncode == 0:
                console.success("\n✅ Evaluation completed successfully!")
            else:
                console.error(f"\n❌ Evaluation failed (exit code: {process.returncode})")

        except Exception as e:
            console.error(f"Failed to run evaluation: {e}")

        input("\nPress Enter to continue...")

    def _find_main_py(self) -> Optional[Path]:
        """Find main.py file."""
        # Check current directory
        main_py = self.project_root / "main.py"
        if main_py.exists():
            return main_py

        # Check parent directories
        for parent in self.project_root.parents:
            main_py = parent / "main.py"
            if main_py.exists():
                return main_py

        return None

    def _get_input(self, prompt: str) -> str:
        """Get user input with prompt."""
        try:
            return input(f"➤ {prompt}")
        except KeyboardInterrupt:
            raise

    def _select_from_list(self, items: List[Tuple[str, Path]], title: str) -> Optional[int]:
        """Interactive list selection."""
        if not items:
            console.warning(f"No {title.lower()} found")
            return None

        console.info(f"\n{title}:")
        for i, (name, _) in enumerate(items, 1):
            console.info(f"{i}. {name}")

        try:
            value = input(f"➤ {title} number: ")
            num = int(value)
            if 1 <= num <= len(items):
                return num
            else:
                console.warning(f"Please enter a number between 1 and {len(items)}")
                return None
        except (ValueError, KeyboardInterrupt):
            return None

    def _confirm(self, message: str) -> bool:
        """Get yes/no confirmation."""
        response = self._get_input(f"{message} (y/n): ").lower()
        return response in ['y', 'yes']

    def _get_category_name(self, category: int) -> str:
        """Get category name."""
        names = {0: "Deterministic", 1: "LLM Judge", 2: "Agent Scorer", 3: "Trajectory"}
        return names.get(category, "Unknown")

    def _get_type_name(self, eval_type: int) -> str:
        """Get type name."""
        names = {
            0: "Unknown", 1: "Exact Match", 2: "Contains", 3: "Regex",
            4: "Factuality", 5: "Custom", 6: "JSON Similarity", 7: "Trajectory"
        }
        return names.get(eval_type, "Unknown")

    def _drill_down_eval_sets(self) -> None:
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

    def _drill_down_evaluators(self) -> None:
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

    def _show_no_items_screen(self, item_type: str) -> None:
        """Show no items screen."""
        self._clear_screen()
        console.warning(f"No {item_type} found!")
        console.info("Press Enter to go back...")
        self._get_input("")

    def _show_eval_set_preview(self, path: Path) -> None:
        """Show eval set preview info."""
        try:
            with open(path) as f:
                data = json.load(f)
            test_count = len(data.get("evaluations", []))
            evaluator_count = len(data.get("evaluatorRefs", []))
            console.info(f"    📄 {path.name}")
            console.info(f"    📊 Tests: {test_count} | Evaluators: {evaluator_count}")
        except Exception:
            console.info(f"    📄 {path.name} (error loading)")

    def _show_evaluator_preview(self, path: Path) -> None:
        """Show evaluator preview info."""
        try:
            with open(path) as f:
                data = json.load(f)
            category = self._get_category_name(data.get("category", 0))
            type_name = self._get_type_name(data.get("type", 1))
            console.info(f"    📄 {path.name}")
            console.info(f"    🎯 Type: {category} | {type_name}")
        except Exception:
            console.info(f"    📄 {path.name} (error loading)")

    def _show_eval_set_details(self, eval_set_tuple: Tuple[str, Path]) -> None:
        """Show detailed eval set view."""
        name, path = eval_set_tuple
        self._clear_screen()
        console.info(f"📋 Eval Set Details: {name}")
        console.info("─" * 65)

        try:
            with open(path) as f:
                data = json.load(f)

            console.info(f"📄 File: {path.name}")
            console.info(f"🆔 ID: {data.get('id', 'Unknown')}")
            console.info(f"📊 Tests: {len(data.get('evaluations', []))}")
            console.info(f"⚙️  Evaluators: {len(data.get('evaluatorRefs', []))}")
            console.info(f"📦 Batch Size: {data.get('batchSize', 'Unknown')}")
            console.info(f"⏱️  Timeout: {data.get('timeoutMinutes', 'Unknown')} minutes")

            evaluator_refs = data.get('evaluatorRefs', [])
            if evaluator_refs:
                console.info("\n🎯 Evaluator References:")
                for ref in evaluator_refs:
                    console.info(f"   • {ref}")

            evaluations = data.get('evaluations', [])
            if evaluations:
                console.info("\n📝 Test Cases:")
                for i, eval_data in enumerate(evaluations[:10], 1):  # Show first 10
                    test_name = eval_data.get('name', f'Test {i}')
                    console.info(f"   {i}. {test_name}")
                    if 'inputs' in eval_data:
                        inputs_preview = str(eval_data['inputs'])[:60]
                        if len(str(eval_data['inputs'])) > 60:
                            inputs_preview += "..."
                        console.info(f"      Input: {inputs_preview}")
                    if 'expectedOutput' in eval_data:
                        output_preview = str(eval_data['expectedOutput'])[:60]
                        if len(str(eval_data['expectedOutput'])) > 60:
                            output_preview += "..."
                        console.info(f"      Expected: {output_preview}")

                if len(evaluations) > 10:
                    console.info(f"   ... and {len(evaluations) - 10} more tests")

        except Exception as e:
            console.error(f"Error loading eval set: {e}")

        console.info("\n⌨️  Press q/Backspace to go back...")
        while True:
            key = self._get_key_input()
            if key in ['q', 'Q', 'back']:
                break

    def _show_evaluator_details(self, evaluator_tuple: Tuple[str, Path]) -> None:
        """Show detailed evaluator view."""
        name, path = evaluator_tuple
        self._clear_screen()
        console.info(f"⚙️  Evaluator Details: {name}")
        console.info("─" * 65)

        try:
            with open(path) as f:
                data = json.load(f)

            console.info(f"📄 File: {path.name}")
            console.info(f"🆔 ID: {data.get('id', 'Unknown')}")
            console.info(f"📝 Description: {data.get('description', 'No description')}")
            console.info(f"🏷️  Category: {self._get_category_name(data.get('category', 0))}")
            console.info(f"🎯 Type: {self._get_type_name(data.get('type', 1))}")
            console.info(f"🔍 Target Key: {data.get('targetOutputKey', '*')}")

            if 'llmConfig' in data:
                llm_config = data['llmConfig']
                console.info("\n🤖 LLM Configuration:")
                console.info(f"   Model: {llm_config.get('modelName', 'Unknown')}")
                if 'prompt' in llm_config:
                    prompt_preview = llm_config['prompt'][:100]
                    if len(llm_config['prompt']) > 100:
                        prompt_preview += "..."
                    console.info(f"   Prompt: {prompt_preview}")

        except Exception as e:
            console.error(f"Error loading evaluator: {e}")

        console.info("\n⌨️  Press q/Backspace to go back...")
        while True:
            key = self._get_key_input()
            if key in ['q', 'Q', 'back']:
                break

    def _create_eval_set(self) -> None:
        """Create new evaluation set interactively."""
        console.info("\n➕ Create New Eval Set")

        name = self._get_input("Name: ")
        if not name:
            return

        # Create clean filename from name
        filename = f"{name.lower().replace(' ', '_')}.json"

        # Create basic eval set
        eval_set = {
            "id": f"eval-{len(self.eval_sets) + 1}",
            "fileName": filename,
            "evaluatorRefs": [],
            "name": name,
            "batchSize": 10,
            "timeoutMinutes": 20,
            "modelSettings": [],
            "createdAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "updatedAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "evaluations": []
        }

        # Ask if they want to add evaluations
        add_evals = self._get_input("Add evaluations now? (y/n): ").lower()
        if add_evals in ['y', 'yes']:
            eval_set["evaluations"] = self._add_evaluations_interactive(str(eval_set["id"]))

        # Ensure evaluationSets directory exists
        eval_sets_dir = self.project_root / "evaluationSets"
        eval_sets_dir.mkdir(exist_ok=True)

        # Save file
        file_path = eval_sets_dir / filename

        with open(file_path, 'w') as f:
            json.dump(eval_set, f, indent=2)

        console.success(f"✅ Created eval set: {filename}")
        self._discover_files()  # Refresh

    def _create_eval_set_interactive(self) -> None:
        """Create new evaluation set with comprehensive questions."""
        self._clear_screen()
        console.info("➕ Create New Eval Set - Interactive Wizard")
        console.info("─" * 65)

        # Basic Information
        console.info("📝 Basic Information")
        name = input("➤ Eval Set Name: ").strip()
        if not name:
            console.warning("Name is required!")
            input("Press Enter to continue...")
            return

        # Create clean filename from name
        filename = f"{name.lower().replace(' ', '_')}.json"

        # Evaluator References
        console.info("\n🎯 Evaluator References")
        console.info("Available evaluators:")
        for i, (eval_name, _) in enumerate(self.evaluators, 1):
            console.info(f"  {i}. {eval_name}")

        evaluator_refs = []
        if self.evaluators:
            refs_input = input("➤ Select evaluators (comma-separated numbers, or 'all'): ").strip()
            if refs_input.lower() == 'all':
                evaluator_refs = [self._get_evaluator_id(path) for eval_name, path in self.evaluators]
            elif refs_input:
                try:
                    for num in refs_input.split(','):
                        idx = int(num.strip()) - 1
                        if 0 <= idx < len(self.evaluators):
                            eval_path = self.evaluators[idx][1]
                            eval_id = self._get_evaluator_id(eval_path)
                            evaluator_refs.append(eval_id)
                except ValueError:
                    console.warning("Invalid input, no evaluators selected")

        # Test Cases
        console.info("\n📝 Test Cases")
        evaluations = []
        test_count = 1

        while True:
            console.info(f"\nTest Case #{test_count}")
            test_name = input("➤ Test Name (or 'done' to finish): ").strip()
            if test_name.lower() == 'done':
                break

            if not test_name:
                console.warning("Test name is required!")
                continue

            # Inputs
            console.info("📥 Inputs (JSON format)")
            console.info("Examples: {\"a\": 5, \"b\": 3} or {\"query\": \"hello world\"}")
            inputs_str = input("➤ Inputs: ").strip()
            try:
                inputs = json.loads(inputs_str) if inputs_str else {}
            except json.JSONDecodeError:
                console.warning("Invalid JSON, using empty inputs")
                inputs = {}

            # Expected Output
            console.info("📤 Expected Output (JSON format)")
            expected_str = input("➤ Expected Output: ").strip()
            try:
                expected_output = json.loads(expected_str) if expected_str else {}
            except json.JSONDecodeError:
                console.warning("Invalid JSON, using empty expected output")
                expected_output = {}

            evaluation: Dict[str, Any] = {
                "id": f"test-{test_count}",
                "name": test_name,
                "inputs": inputs,
                "expectedOutput": expected_output,
                "expectedAgentBehavior": "",
                "simulationInstructions": "",
                "simulateInput": False,
                "inputGenerationInstructions": "",
                "simulateTools": False,
                "toolsToSimulate": [],
                "evalSetId": f"eval-{len(self.eval_sets) + 1}",
                "createdAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "updatedAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
            evaluations.append(evaluation)
            test_count += 1

        if not evaluations:
            console.warning("At least one test case is required!")
            input("Press Enter to continue...")
            return

        # Create eval set
        eval_set = {
            "id": f"eval-{len(self.eval_sets) + 1}",
            "fileName": filename,
            "evaluatorRefs": evaluator_refs,
            "name": name,
            "batchSize": 10,
            "timeoutMinutes": 20,
            "modelSettings": [],
            "createdAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "updatedAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "evaluations": evaluations
        }

        # Ensure evaluationSets directory exists
        eval_sets_dir = self.project_root / "evaluationSets"
        eval_sets_dir.mkdir(exist_ok=True)

        # Save file
        file_path = eval_sets_dir / filename

        try:
            with open(file_path, 'w') as f:
                json.dump(eval_set, f, indent=2)

            console.success(f"\n✅ Created eval set: {filename}")
            console.info(f"📊 Tests: {len(evaluations)}")
            console.info(f"⚙️  Evaluators: {len(evaluator_refs)}")

            self._discover_files()  # Refresh
        except Exception as e:
            console.error(f"Failed to create eval set: {e}")

        input("\nPress Enter to continue...")

    def _add_evaluations_interactive(self, eval_set_id: str) -> List[Dict[str, Any]]:
        """Add evaluations interactively."""
        evaluations = []
        test_count = 1

        while True:
            console.info(f"\nTest Case #{test_count}")
            test_name = self._get_input("Test Name (or 'done' to finish): ")
            if test_name.lower() == 'done':
                break

            if not test_name:
                console.warning("Test name is required!")
                continue

            # Simple inputs
            console.info("Inputs (JSON format, e.g., {\"a\": 5, \"b\": 3})")
            inputs_str = self._get_input("Inputs: ")
            try:
                inputs = json.loads(inputs_str) if inputs_str else {}
            except json.JSONDecodeError:
                console.warning("Invalid JSON, using empty inputs")
                inputs = {}

            # Expected output
            console.info("Expected Output (JSON format)")
            expected_str = self._get_input("Expected Output: ")
            try:
                expected_output = json.loads(expected_str) if expected_str else {}
            except json.JSONDecodeError:
                console.warning("Invalid JSON, using empty expected output")
                expected_output = {}

            evaluation: Dict[str, Any] = {
                "id": f"test-{test_count}",
                "name": test_name,
                "inputs": inputs,
                "expectedOutput": expected_output,
                "expectedAgentBehavior": "",
                "simulationInstructions": "",
                "simulateInput": False,
                "inputGenerationInstructions": "",
                "simulateTools": False,
                "toolsToSimulate": [],
                "evalSetId": eval_set_id,
                "createdAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "updatedAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
            evaluations.append(evaluation)
            test_count += 1

        return evaluations

    def _create_evaluator(self) -> None:
        """Create new evaluator interactively."""
        console.info("\n➕ Create New Evaluator")

        # Select template
        console.info("Templates:")
        console.info("1. Exact Match")
        console.info("2. JSON Similarity")

        template = self._get_number_input("Template (1-2): ", 1, 2)
        if template is None:
            return

        name = self._get_input("Name: ")
        if not name:
            return

        # Template configurations
        if template == 1:
            evaluator = {
                "id": f"eval-{name.lower().replace(' ', '-')}",
                "name": name,
                "description": "Exact match evaluator",
                "category": 0,
                "type": 1,
                "targetOutputKey": "*",
                "createdAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "updatedAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
        else:  # JSON Similarity
            evaluator = {
                "id": f"eval-{name.lower().replace(' ', '-')}",
                "name": name,
                "description": "JSON similarity evaluator",
                "category": 0,
                "type": 6,
                "targetOutputKey": "*",
                "createdAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "updatedAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }

        # Ensure evaluators directory exists
        evaluators_dir = self.project_root / "evaluators"
        evaluators_dir.mkdir(exist_ok=True)

        # Save file
        filename = f"{name.lower().replace(' ', '_')}.json"
        file_path = evaluators_dir / filename

        with open(file_path, 'w') as f:
            json.dump(evaluator, f, indent=2)

        console.success(f"✅ Created evaluator: {filename}")
        self._discover_files()  # Refresh

    def _create_evaluator_interactive(self) -> None:
        """Create new evaluator with comprehensive questions."""
        self._clear_screen()
        console.info("➕ Create New Evaluator - Interactive Wizard")
        console.info("─" * 65)

        # Basic Information
        console.info("📝 Basic Information")
        name = input("➤ Evaluator Name: ").strip()
        if not name:
            console.warning("Name is required!")
            input("Press Enter to continue...")
            return

        description = input("➤ Description: ").strip() or f"{name} evaluator"

        # Category Selection
        console.info("\n🏷️ Category Selection")
        categories = {
            0: "Deterministic",
            1: "LLM as Judge",
            2: "Agent Scorer",
            3: "Trajectory"
        }

        for key, value in categories.items():
            console.info(f"  {key}. {value}")

        try:
            category = int(input("➤ Select Category (0-3): ") or "0")
            if category not in categories:
                category = 0
        except ValueError:
            category = 0

        # Type Selection
        console.info(f"\n🎯 Type Selection (Category: {categories[category]})")
        types = {
            0: "Unknown", 1: "Exact Match", 2: "Contains", 3: "Regex",
            4: "Factuality", 5: "Custom", 6: "JSON Similarity", 7: "Trajectory"
        }

        # Show relevant types based on category
        relevant_types = []
        if category == 0:  # Deterministic
            relevant_types = [1, 2, 3, 6]  # Exact Match, Contains, Regex, JSON Similarity
        elif category == 1:  # LLM as Judge
            relevant_types = [4, 5]  # Factuality, Custom
        elif category == 3:  # Trajectory
            relevant_types = [7]  # Trajectory
        else:
            relevant_types = list(types.keys())

        for type_id in relevant_types:
            console.info(f"  {type_id}. {types[type_id]}")

        try:
            eval_type = int(input(f"➤ Select Type ({', '.join(map(str, relevant_types))}): ") or str(relevant_types[0]))
            if eval_type not in relevant_types:
                eval_type = relevant_types[0]
        except (ValueError, IndexError):
            eval_type = 1

        # Target Output Key
        console.info("\n🔍 Target Configuration")
        console.info("Target Output Key determines which part of the output to evaluate")
        console.info("Examples: '*' (all), 'result', 'answer', 'output'")
        target_key = input("➤ Target Output Key (default: '*'): ").strip() or "*"

        # Create basic evaluator
        evaluator = {
            "id": f"eval-{name.lower().replace(' ', '-')}",
            "name": name,
            "description": description,
            "category": category,
            "type": eval_type,
            "targetOutputKey": target_key,
            "createdAt": "2025-01-25T00:00:00Z",
            "updatedAt": "2025-01-25T00:00:00Z"
        }

        # LLM Configuration (if LLM as Judge)
        if category == 1:  # LLM as Judge
            console.info("\n🤖 LLM Configuration")
            model_name = input("➤ Model Name (default: gpt-4): ").strip() or "gpt-4"

            console.info("📝 Evaluation Prompt")
            console.info("This prompt will be used to evaluate the agent's output")
            prompt = input("➤ Evaluation Prompt: ").strip()

            if prompt:
                evaluator["llmConfig"] = {
                    "modelName": model_name,
                    "prompt": prompt,
                    "temperature": 0.0,
                    "maxTokens": 1000
                }

        # Ensure evaluators directory exists
        evaluators_dir = self.project_root / "evaluators"
        evaluators_dir.mkdir(exist_ok=True)

        # Save file
        filename = f"{name.lower().replace(' ', '_')}.json"
        file_path = evaluators_dir / filename

        try:
            with open(file_path, 'w') as f:
                json.dump(evaluator, f, indent=2)

            console.success(f"\n✅ Created evaluator: {filename}")
            console.info(f"🏷️  Category: {categories[category]}")
            console.info(f"🎯 Type: {types[eval_type]}")
            console.info(f"🔍 Target: {target_key}")

            self._discover_files()  # Refresh
        except Exception as e:
            console.error(f"Failed to create evaluator: {e}")

        input("\nPress Enter to continue...")

    def _get_number_input(self, prompt: str, min_val: int, max_val: int) -> Optional[int]:
        """Get number input with validation."""
        try:
            value = input(f"➤ {prompt}")
            num = int(value)
            if min_val <= num <= max_val:
                return num
            else:
                console.warning(f"Please enter a number between {min_val} and {max_val}")
                return None
        except (ValueError, KeyboardInterrupt):
            return None

    def _get_evaluator_id(self, path: Path) -> str:
        """Get evaluator ID from file."""
        try:
            with open(path) as f:
                data = json.load(f)
            return data.get("id", path.stem)
        except Exception:
            return path.stem


def launch_interactive_cli(project_root: Optional[Path] = None) -> None:
    """Launch the interactive CLI."""
    cli = InteractiveEvalCLI(project_root)
    cli.run()
