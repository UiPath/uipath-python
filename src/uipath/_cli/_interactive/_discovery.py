"""Discovery utilities for finding eval sets and evaluators."""
# type: ignore

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._main import InteractiveEvalCLI


class DiscoveryMixin:
    """Mixin for file discovery operations."""

    def _discover_files(self: "InteractiveEvalCLI") -> None:
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
