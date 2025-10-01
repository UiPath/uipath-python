"""Eval set operations for interactive CLI."""
# type: ignore

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

from .._utils._console import ConsoleLogger

if TYPE_CHECKING:
    from ._main import InteractiveEvalCLI

console = ConsoleLogger()


class EvalSetMixin:
    """Mixin for eval set operations."""

    def _create_eval_set_simple(self: "InteractiveEvalCLI") -> None:
        """Create new evaluation set - simplified version."""
        self._clear_screen()
        console.info("➕ Create New Eval Set")
        console.info("─" * 65)

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
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "updatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "evaluations": [],
        }

        # Ask if they want to add evaluations
        add_evals = self._get_input("Add evaluations now? (y/n): ").lower()
        if add_evals in ["y", "yes"]:
            eval_set["evaluations"] = self._add_evaluations_interactive(
                str(eval_set["id"])
            )

        # Ensure evaluationSets directory exists
        eval_sets_dir = self.project_root / "evaluationSets"
        eval_sets_dir.mkdir(exist_ok=True)

        # Save file
        file_path = eval_sets_dir / filename

        with open(file_path, "w") as f:
            json.dump(eval_set, f, indent=2)

        console.success(f"✅ Created eval set: {filename}")
        self._discover_files()  # Refresh

    def _create_eval_set_interactive(self: "InteractiveEvalCLI") -> None:
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
            refs_input = input(
                "➤ Select evaluators (comma-separated numbers, or 'all'): "
            ).strip()
            if refs_input.lower() == "all":
                evaluator_refs = [
                    self._get_evaluator_id(path) for eval_name, path in self.evaluators
                ]
            elif refs_input:
                try:
                    for num in refs_input.split(","):
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
            if test_name.lower() == "done":
                break

            if not test_name:
                console.warning("Test name is required!")
                continue

            # Inputs
            console.info("📥 Inputs (JSON format)")
            console.info('Examples: {"a": 5, "b": 3} or {"query": "hello world"}')
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
                "createdAt": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "updatedAt": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
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
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "updatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "evaluations": evaluations,
        }

        # Ensure evaluationSets directory exists
        eval_sets_dir = self.project_root / "evaluationSets"
        eval_sets_dir.mkdir(exist_ok=True)

        # Save file
        file_path = eval_sets_dir / filename

        try:
            with open(file_path, "w") as f:
                json.dump(eval_set, f, indent=2)

            console.success(f"\n✅ Created eval set: {filename}")
            console.info(f"📊 Tests: {len(evaluations)}")
            console.info(f"⚙️  Evaluators: {len(evaluator_refs)}")

            self._discover_files()  # Refresh
        except Exception as e:
            console.error(f"Failed to create eval set: {e}")

        input("\nPress Enter to continue...")

    def _add_evaluations_interactive(
        self: "InteractiveEvalCLI", eval_set_id: str
    ) -> List[Dict[str, Any]]:
        """Add evaluations interactively."""
        evaluations = []
        test_count = 1

        while True:
            console.info(f"\nTest Case #{test_count}")
            test_name = self._get_input("Test Name (or 'done' to finish): ")
            if test_name.lower() == "done":
                break

            if not test_name:
                console.warning("Test name is required!")
                continue

            # Inputs
            console.info("📥 Inputs (JSON format)")
            console.info('Examples: {"a": 5, "b": 3} or {"query": "hello world"}')
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
                "evalSetId": eval_set_id,
                "createdAt": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
                "updatedAt": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            }
            evaluations.append(evaluation)
            test_count += 1

        return evaluations

    def _list_eval_sets(self: "InteractiveEvalCLI") -> None:
        """List available eval sets."""
        console.info("\n📋 Available Eval Sets:")
        if not self.eval_sets:
            console.warning("No eval sets found")
            return

        for i, (name, path) in enumerate(self.eval_sets, 1):
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

    def _show_eval_set_preview(self: "InteractiveEvalCLI", path: Path) -> None:
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

    def _show_eval_set_details(
        self: "InteractiveEvalCLI", eval_set_tuple: tuple[str, Path]
    ) -> None:
        """Show detailed eval set view."""
        name, path = eval_set_tuple
        self._clear_screen()
        console.info(f"📋 Eval Set Details: {name}")
        console.info("─" * 65)

        try:
            with open(path) as f:
                data = json.load(f)

            console.info(f"\n📄 {path.name}")
            console.info(f"🆔 ID: {data.get('id', 'Unknown')}")
            console.info(f"📊 Tests: {len(data.get('evaluations', []))}")
            console.info(f"⚙️  Evaluators: {len(data.get('evaluatorRefs', []))}")
            console.info(f"📦 Batch Size: {data.get('batchSize', 'Unknown')}")
            console.info(f"⏱️  Timeout: {data.get('timeoutMinutes', 'Unknown')} minutes")

            evaluator_refs = data.get("evaluatorRefs", [])
            if evaluator_refs:
                console.info("\n🎯 Evaluator References:")
                for ref in evaluator_refs:
                    console.info(f"   • {ref}")

            evaluations = data.get("evaluations", [])
            if evaluations:
                console.info("\n📝 Test Cases:")
                for i, eval_data in enumerate(evaluations[:10], 1):  # Show first 10
                    test_name = eval_data.get("name", f"Test {i}")
                    console.info(f"   {i}. {test_name}")
                    if "inputs" in eval_data:
                        inputs_preview = str(eval_data["inputs"])[:60]
                        if len(str(eval_data["inputs"])) > 60:
                            inputs_preview += "..."
                        console.info(f"      Input: {inputs_preview}")
                    if "expectedOutput" in eval_data:
                        output_preview = str(eval_data["expectedOutput"])[:60]
                        if len(str(eval_data["expectedOutput"])) > 60:
                            output_preview += "..."
                        console.info(f"      Expected: {output_preview}")

                if len(evaluations) > 10:
                    console.info(f"\n   ... and {len(evaluations) - 10} more tests")

        except Exception as e:
            console.error(f"Error loading eval set: {e}")

        console.info("\n💡 Press Backspace to go back")
        self._get_key_input()
