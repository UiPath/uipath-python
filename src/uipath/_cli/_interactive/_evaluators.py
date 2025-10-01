"""Evaluator operations for interactive CLI."""
# type: ignore

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .._utils._console import ConsoleLogger

if TYPE_CHECKING:
    from ._main import InteractiveEvalCLI

console = ConsoleLogger()


class EvaluatorMixin:
    """Mixin for evaluator operations."""

    def _create_evaluator_simple(self: "InteractiveEvalCLI") -> None:
        """Create new evaluator - simplified version."""
        self._clear_screen()
        console.info("➕ Create New Evaluator")
        console.info("─" * 65)

        name = self._get_input("Name: ")
        if not name:
            return

        # Create basic evaluator
        evaluator = {
            "id": f"eval-{name.lower().replace(' ', '-')}",
            "name": name,
            "description": f"{name} evaluator",
            "category": 0,
            "type": 1,
            "targetOutputKey": "*",
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "updatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        # Ensure evaluators directory exists
        evaluators_dir = self.project_root / "evaluators"
        evaluators_dir.mkdir(exist_ok=True)

        # Save file
        filename = f"{name.lower().replace(' ', '_')}.json"
        file_path = evaluators_dir / filename

        with open(file_path, "w") as f:
            json.dump(evaluator, f, indent=2)

        console.success(f"✅ Created evaluator: {filename}")
        self._discover_files()  # Refresh

    def _create_evaluator_interactive(self: "InteractiveEvalCLI") -> None:
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
            3: "Trajectory",
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
            0: "Unknown",
            1: "Exact Match",
            2: "Contains",
            3: "Regex",
            4: "Factuality",
            5: "Custom",
            6: "JSON Similarity",
            7: "Trajectory",
        }

        # Show relevant types based on category
        relevant_types = []
        if category == 0:  # Deterministic
            relevant_types = [
                1,
                2,
                3,
                6,
            ]  # Exact Match, Contains, Regex, JSON Similarity
        elif category == 1:  # LLM as Judge
            relevant_types = [4, 5]  # Factuality, Custom
        elif category == 3:  # Trajectory
            relevant_types = [7]  # Trajectory
        else:
            relevant_types = list(types.keys())

        for type_id in relevant_types:
            console.info(f"  {type_id}. {types[type_id]}")

        try:
            eval_type = int(
                input(f"➤ Select Type ({', '.join(map(str, relevant_types))}): ")
                or str(relevant_types[0])
            )
            if eval_type not in relevant_types:
                eval_type = relevant_types[0]
        except (ValueError, IndexError):
            eval_type = 1

        # Target Output Key
        console.info("\n🔍 Target Configuration")
        console.info(
            "Target Output Key determines which part of the output to evaluate"
        )
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
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "updatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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
                    "maxTokens": 1000,
                }

        # Ensure evaluators directory exists
        evaluators_dir = self.project_root / "evaluators"
        evaluators_dir.mkdir(exist_ok=True)

        # Save file
        filename = f"{name.lower().replace(' ', '_')}.json"
        file_path = evaluators_dir / filename

        try:
            with open(file_path, "w") as f:
                json.dump(evaluator, f, indent=2)

            console.success(f"\n✅ Created evaluator: {filename}")
            console.info(f"🏷️  Category: {categories[category]}")
            console.info(f"🎯 Type: {types[eval_type]}")
            console.info(f"🔍 Target: {target_key}")

            self._discover_files()  # Refresh
        except Exception as e:
            console.error(f"Failed to create evaluator: {e}")

        input("\nPress Enter to continue...")

    def _list_evaluators(self: "InteractiveEvalCLI") -> None:
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

    def _show_evaluator_preview(self: "InteractiveEvalCLI", path: Path) -> None:
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

    def _show_evaluator_details(
        self: "InteractiveEvalCLI", evaluator_tuple: tuple[str, Path]
    ) -> None:
        """Show detailed evaluator view."""
        name, path = evaluator_tuple
        self._clear_screen()
        console.info(f"⚙️  Evaluator Details: {name}")
        console.info("─" * 65)

        try:
            with open(path) as f:
                data = json.load(f)

            console.info(f"\n📄 {path.name}")
            console.info(f"🆔 ID: {data.get('id', 'Unknown')}")
            console.info(f"📝 Description: {data.get('description', 'No description')}")
            console.info(
                f"🏷️  Category: {self._get_category_name(data.get('category', 0))}"
            )
            console.info(f"🎯 Type: {self._get_type_name(data.get('type', 1))}")
            console.info(f"🔍 Target Key: {data.get('targetOutputKey', '*')}")

            if "llmConfig" in data:
                llm_config = data["llmConfig"]
                console.info("\n🤖 LLM Configuration:")
                console.info(f"   Model: {llm_config.get('modelName', 'Unknown')}")
                if "prompt" in llm_config:
                    prompt_preview = llm_config["prompt"][:100]
                    if len(llm_config["prompt"]) > 100:
                        prompt_preview += "..."
                    console.info(f"   Prompt: {prompt_preview}")

        except Exception as e:
            console.error(f"Error loading evaluator: {e}")

        console.info("\n💡 Press Backspace to go back")
        self._get_key_input()

    def _get_category_name(self: "InteractiveEvalCLI", category: int) -> str:
        """Get category name from number."""
        categories = {
            0: "Deterministic",
            1: "LLM as Judge",
            2: "Agent Scorer",
            3: "Trajectory",
        }
        return categories.get(category, "Unknown")

    def _get_type_name(self: "InteractiveEvalCLI", eval_type: int) -> str:
        """Get type name from number."""
        types = {
            0: "Unknown",
            1: "Exact Match",
            2: "Contains",
            3: "Regex",
            4: "Factuality",
            5: "Custom",
            6: "JSON Similarity",
            7: "Trajectory",
        }
        return types.get(eval_type, "Unknown")

    def _get_evaluator_id(self: "InteractiveEvalCLI", path: Path) -> str:
        """Get evaluator ID from file."""
        try:
            with open(path) as f:
                data = json.load(f)
            return data.get("id", path.stem)
        except Exception:
            return path.stem
