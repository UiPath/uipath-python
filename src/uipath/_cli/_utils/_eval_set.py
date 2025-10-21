import json
from pathlib import Path
from typing import List, Optional

import click

from uipath._cli._evals._models._evaluation_set import EvaluationSet
from uipath._cli._utils._console import ConsoleLogger

console = ConsoleLogger()


class EvalHelpers:
    @staticmethod
    def auto_discover_eval_set() -> str:
        """Auto-discover evaluation set from evals/eval-sets directory.

        Returns:
            Path to the evaluation set file

        Raises:
            ValueError: If no eval set found or multiple eval sets exist
        """
        eval_sets_dir = Path("evals/eval-sets")

        if not eval_sets_dir.exists():
            raise ValueError(
                "No 'evals/eval-sets' directory found. "
                "Please set 'UIPATH_PROJECT_ID' env var and run 'uipath pull'."
            )

        eval_set_files = list(eval_sets_dir.glob("*.json"))

        if not eval_set_files:
            raise ValueError(
                "No evaluation set files found in 'evals/eval-sets' directory. "
            )

        if len(eval_set_files) > 1:
            file_names = [f.name for f in eval_set_files]
            raise ValueError(
                f"Multiple evaluation sets found: {file_names}. "
                f"Please specify which evaluation set to use: 'uipath eval [entrypoint] <eval_set_path>'"
            )

        eval_set_path = str(eval_set_files[0])
        console.info(
            f"Auto-discovered evaluation set: {click.style(eval_set_path, fg='cyan')}"
        )

        eval_set_path_obj = Path(eval_set_path)
        if not eval_set_path_obj.is_file() or eval_set_path_obj.suffix != ".json":
            raise ValueError("Evaluation set must be a JSON file")

        return eval_set_path

    @staticmethod
    def load_eval_set(
        eval_set_path: str, eval_ids: Optional[List[str]] = None
    ) -> EvaluationSet:
        """Load the evaluation set from file.

        Returns:
            The loaded evaluation set as EvaluationSet model
        """
        try:
            with open(eval_set_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON in evaluation set file '{eval_set_path}': {str(e)}. "
                f"Please check the file for syntax errors."
            ) from e

        try:
            eval_set = EvaluationSet(**data)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Invalid evaluation set format in '{eval_set_path}': {str(e)}. "
                f"Please verify the evaluation set structure."
            ) from e
        if eval_ids:
            eval_set.extract_selected_evals(eval_ids)
        return eval_set
