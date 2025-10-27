import json
from pathlib import Path
from typing import List, Optional

import click
from pydantic import TypeAdapter, ValidationError

from uipath._cli._evals._models._evaluation_set import (
    EvaluationItem,
    EvaluationSet,
    LegacyEvaluationItem,
    LegacyEvaluationSet,
)
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
    ) -> tuple[EvaluationSet, str]:
        """Load the evaluation set from file.

        Args:
            eval_set_path: Path to the evaluation set file
            eval_ids: Optional list of evaluation IDs to filter

        Returns:
            Tuple of (EvaluationSet, resolved_path)
        """
        # If the file doesn't exist at the given path, try looking in evals/eval-sets/
        resolved_path = eval_set_path
        if not Path(eval_set_path).exists():
            # Check if it's just a filename, then search in evals/eval-sets/
            if Path(eval_set_path).name == eval_set_path:
                eval_sets_path = Path("evals/eval-sets") / eval_set_path
                if eval_sets_path.exists():
                    resolved_path = str(eval_sets_path)

        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError as e:
            raise ValueError(
                f"Evaluation set file not found: '{eval_set_path}'. "
                f"Searched in current directory and evals/eval-sets/ directory."
            ) from e
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON in evaluation set file '{resolved_path}': {str(e)}. "
                f"Please check the file for syntax errors."
            ) from e

        try:
            eval_set: EvaluationSet | LegacyEvaluationSet = TypeAdapter(
                EvaluationSet | LegacyEvaluationSet
            ).validate_python(data)
            if isinstance(eval_set, LegacyEvaluationSet):

                def migrate_evaluation_item(
                    evaluation: LegacyEvaluationItem, evaluators: list[str]
                ) -> EvaluationItem:
                    return EvaluationItem.model_validate(
                        {
                            "id": evaluation.id,
                            "name": evaluation.name,
                            "inputs": evaluation.inputs,
                            "expectedAgentBehavior": evaluation.expected_agent_behavior,
                            "mockingStrategy": evaluation.mocking_strategy,
                            "evaluationCriterias": {
                                k: {
                                    "expectedOutput": evaluation.expected_output,
                                    "expectedAgentBehavior": evaluation.expected_agent_behavior,
                                }
                                for k in evaluators
                            },
                        }
                    )

                eval_set = EvaluationSet(
                    id=eval_set.id,
                    name=eval_set.name,
                    evaluator_refs=eval_set.evaluator_refs,
                    evaluations=[
                        migrate_evaluation_item(evaluation, eval_set.evaluator_refs)
                        for evaluation in eval_set.evaluations
                    ],
                )
        except ValidationError as e:
            raise ValueError(
                f"Invalid evaluation set format in '{resolved_path}': {str(e)}. "
                f"Please verify the evaluation set structure."
            ) from e
        if eval_ids:
            eval_set.extract_selected_evals(eval_ids)
        return eval_set, resolved_path
