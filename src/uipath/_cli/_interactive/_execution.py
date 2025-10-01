"""Execution utilities for running evaluations."""
# type: ignore

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .._utils._console import ConsoleLogger

if TYPE_CHECKING:
    from ._main import InteractiveEvalCLI

console = ConsoleLogger()


class ExecutionMixin:
    """Mixin for execution operations."""

    def _execute_evaluation(self: "InteractiveEvalCLI", eval_path: Path) -> None:
        """Execute evaluation with live results."""
        console.info("\n🚀 Running evaluation...")

        # Find main.py
        main_py = self._find_main_py()
        if not main_py:
            console.error("Could not find main.py")
            return

        # Build command - run from the project directory
        cmd = [
            sys.executable,
            "-m",
            "uipath._cli.cli_eval",
            str(main_py.relative_to(self.project_root)),
            str(eval_path.relative_to(self.project_root)),
            "--no-report",
            "--workers",
            "1",
        ]

        console.info(
            f"💻 Command: uipath eval {main_py.name} {eval_path.name} --no-report"
        )

        try:
            # Run with real-time output from project directory
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=self.project_root,
            )

            # Stream output in real-time
            if process.stdout:
                for line in process.stdout:
                    print(line.rstrip())

            process.wait()

            if process.returncode == 0:
                console.success("\n✅ Evaluation completed successfully!")
            else:
                console.error(
                    f"\n❌ Evaluation failed (exit code: {process.returncode})"
                )

        except Exception as e:
            console.error(f"Failed to run evaluation: {e}")

    def _execute_evaluation_no_clear(
        self: "InteractiveEvalCLI", eval_path: Path
    ) -> None:
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
            sys.executable,
            "-m",
            "uipath._cli.cli_eval",
            str(main_py.relative_to(self.project_root)),
            str(eval_path.relative_to(self.project_root)),
            "--no-report",
            "--workers",
            "1",
        ]

        console.info(
            f"💻 Command: uipath eval {main_py.name} {eval_path.name} --no-report"
        )

        try:
            # Run with real-time output from project directory
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                cwd=self.project_root,
            )

            # Stream output in real-time
            if process.stdout:
                for line in process.stdout:
                    print(line.rstrip())

            process.wait()

            if process.returncode == 0:
                console.success("\n✅ Evaluation completed successfully!")
            else:
                console.error(
                    f"\n❌ Evaluation failed (exit code: {process.returncode})"
                )

        except Exception as e:
            console.error(f"Failed to run evaluation: {e}")

        input("\nPress Enter to continue...")

    def _find_main_py(self: "InteractiveEvalCLI") -> Optional[Path]:
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

    def _confirm(self: "InteractiveEvalCLI", prompt: str) -> bool:
        """Ask for confirmation."""
        response = self._get_input(f"{prompt} (y/n): ").lower()
        return response in ["y", "yes"]
