"""Helper functions for evaluation commands, including loading and parsing evaluation sets and evaluators."""

import json
import logging
from pathlib import Path
from typing import Any

import click
from pydantic import ValidationError

from uipath._cli._evals._conversational_utils import UiPathLegacyEvalChatMessagesMapper

from .evaluators.base_evaluator import GenericBaseEvaluator
from .evaluators.evaluator_factory import EvaluatorFactory
from .mocks._types import InputMockingStrategy, LLMMockingStrategy
from .models.evaluation_set import (
    EvaluationItem,
    EvaluationSet,
    LegacyEvaluationItem,
    LegacyEvaluationSet,
)

logger = logging.getLogger(__name__)

EVAL_SETS_DIRECTORY_NAME = "evaluations/eval-sets"


def _apply_file_overrides_to_conversational_inputs(
    conversational_inputs: Any,
    overrides: dict[str, Any],
) -> None:
    """Apply file overrides to conversational input attachments before mapper conversion.

    Extracts file objects from override values (single dict or array), matches them
    to existing attachments by FullName, and replaces attachment fields in-place.
    No-op if there are no file overrides or no matching attachments.
    """
    if not overrides:
        return

    file_overrides: list[dict[str, Any]] = []
    for value in overrides.values():
        if isinstance(value, list):
            file_overrides.extend(f for f in value if isinstance(f, dict) and "ID" in f)
        elif isinstance(value, dict) and "ID" in value:
            file_overrides.append(value)

    if not file_overrides:
        return

    override_by_name = {f["FullName"]: f for f in file_overrides if "FullName" in f}

    def _override_attachments(attachments: list[Any] | None) -> None:
        if not attachments:
            return
        for attachment in attachments:
            override = override_by_name.get(attachment.full_name)
            if override:
                attachment.id = override["ID"]
                if "FullName" in override:
                    attachment.full_name = override["FullName"]
                if "MimeType" in override:
                    attachment.mime_type = override["MimeType"]

    _override_attachments(conversational_inputs.current_user_prompt.attachments)

    for exchange in conversational_inputs.conversation_history:
        for message in exchange:
            if hasattr(message, "attachments"):
                _override_attachments(message.attachments)


def discriminate_eval_set(data: dict[str, Any]) -> EvaluationSet | LegacyEvaluationSet:
    """Discriminate and parse evaluation set based on version field.

    Uses explicit version checking instead of Pydantic's smart union matching
    to avoid incorrect type selection when both types have matching fields.

    Args:
        data: Dictionary containing evaluation set data

    Returns:
        Either EvaluationSet (for version 1.0) or LegacyEvaluationSet
    """
    version = data.get("version")
    if isinstance(version, (int, float, str)) and float(version) >= 1:
        return EvaluationSet.model_validate(data)
    return LegacyEvaluationSet.model_validate(data)


class EvalHelpers:
    """Helper functions for evaluation commands, including loading and parsing evaluation sets and evaluators."""

    @staticmethod
    def auto_discover_eval_set() -> str:
        """Auto-discover evaluation set from {EVAL_SETS_DIRECTORY_NAME} directory.

        Returns:
            Path to the evaluation set file

        Raises:
            ValueError: If no eval set found or multiple eval sets exist
        """
        eval_sets_dir = Path(EVAL_SETS_DIRECTORY_NAME)

        if not eval_sets_dir.exists():
            raise ValueError(
                f"No '{EVAL_SETS_DIRECTORY_NAME}' directory found. "
                "Please set 'UIPATH_PROJECT_ID' env var and run 'uipath pull'."
            )

        eval_set_files = list(eval_sets_dir.glob("*.json"))

        if not eval_set_files:
            raise ValueError(
                f"No evaluation set files found in '{EVAL_SETS_DIRECTORY_NAME}' directory. "
            )

        if len(eval_set_files) > 1:
            file_names = [f.name for f in eval_set_files]
            raise ValueError(
                f"Multiple evaluation sets found: {file_names}. "
                f"Please specify which evaluation set to use: 'uipath eval [entrypoint] <eval_set_path>'"
            )

        eval_set_path = str(eval_set_files[0])
        logger.info(
            f"Auto-discovered evaluation set: {click.style(eval_set_path, fg='cyan')}"
        )

        eval_set_path_obj = Path(eval_set_path)
        if not eval_set_path_obj.is_file() or eval_set_path_obj.suffix != ".json":
            raise ValueError("Evaluation set must be a JSON file")

        return eval_set_path

    @staticmethod
    def load_eval_set(
        eval_set_path: str,
        eval_ids: list[str] | None = None,
        input_overrides: dict[str, Any] | None = None,
    ) -> tuple[EvaluationSet, str]:
        """Load the evaluation set from file.

        Args:
            eval_set_path: Path to the evaluation set file
            eval_ids: Optional list of evaluation IDs to filter
            input_overrides: Optional input field overrides per evaluation ID.
                For conversational agents, file overrides are applied to attachments
                before the legacy-to-messages conversion so that overridden IDs
                are baked into the messages before mapping.

        Returns:
            Tuple of (EvaluationSet, resolved_path)
        """
        # If the file doesn't exist at the given path, try looking in {EVAL_SETS_DIRECTORY_NAME}/
        resolved_path = eval_set_path
        if not Path(eval_set_path).exists():
            # Check if it's just a filename, then search in {EVAL_SETS_DIRECTORY_NAME}/
            if Path(eval_set_path).name == eval_set_path:
                eval_sets_path = Path(EVAL_SETS_DIRECTORY_NAME) / eval_set_path
                if eval_sets_path.exists():
                    resolved_path = str(eval_sets_path)

        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError as e:
            raise ValueError(
                f"Evaluation set file not found: '{eval_set_path}'. "
                f"Searched in current directory and {EVAL_SETS_DIRECTORY_NAME}/ directory."
            ) from e
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON in evaluation set file '{resolved_path}': {str(e)}. "
                f"Please check the file for syntax errors."
            ) from e

        try:
            eval_set = discriminate_eval_set(data)
            if isinstance(eval_set, LegacyEvaluationSet):

                def migrate_evaluation_item(
                    evaluation: LegacyEvaluationItem, evaluators: list[str]
                ) -> EvaluationItem:
                    mocking_strategy = None
                    input_mocking_strategy = None
                    if (
                        evaluation.simulate_input
                        and evaluation.input_generation_instructions
                    ):
                        input_mocking_strategy = InputMockingStrategy(
                            prompt=evaluation.input_generation_instructions,
                        )
                    if evaluation.simulate_tools:
                        mocking_strategy = LLMMockingStrategy(
                            prompt=evaluation.simulation_instructions or "",
                            tools_to_simulate=evaluation.tools_to_simulate or [],
                        )

                    if evaluation.conversational_inputs:
                        overrides_for_eval = (
                            input_overrides.get(evaluation.id, {})
                            if input_overrides
                            else {}
                        )
                        _apply_file_overrides_to_conversational_inputs(
                            evaluation.conversational_inputs,
                            overrides_for_eval,
                        )

                        conversational_messages_input = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_input_to_uipath_message_list(
                            evaluation.conversational_inputs
                        )
                        evaluation.inputs["messages"] = [
                            message.model_dump(by_alias=True, exclude_none=True)
                            for message in conversational_messages_input
                        ]

                    if evaluation.conversational_expected_output:
                        conversational_messages_expected_output = UiPathLegacyEvalChatMessagesMapper.legacy_conversational_eval_output_to_uipath_message_data_list(
                            evaluation.conversational_expected_output
                        )
                        evaluation.expected_output[
                            "uipath__agent_response_messages"
                        ] = [
                            message.model_dump(by_alias=True, exclude_none=True)
                            for message in conversational_messages_expected_output
                        ]

                    return EvaluationItem.model_validate(
                        {
                            "id": evaluation.id,
                            "name": evaluation.name,
                            "inputs": evaluation.inputs,
                            "expectedAgentBehavior": evaluation.expected_agent_behavior,
                            "mockingStrategy": mocking_strategy,
                            "inputMockingStrategy": input_mocking_strategy,
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
                    model_settings=eval_set.model_settings,
                )
        except ValidationError as e:
            raise ValueError(
                f"Invalid evaluation set format in '{resolved_path}': {str(e)}. "
                f"Please verify the evaluation set structure."
            ) from e
        if eval_ids:
            eval_set.extract_selected_evals(eval_ids)
        return eval_set, resolved_path

    @staticmethod
    async def load_evaluators(
        eval_set_path: str,
        evaluation_set: EvaluationSet,
        agent_model: str | None = None,
    ) -> list[GenericBaseEvaluator[Any, Any, Any]]:
        """Load evaluators referenced by the evaluation set."""
        evaluators = []
        if evaluation_set is None:
            raise ValueError("eval_set cannot be None")
        evaluators_dir = Path(eval_set_path).parent.parent / "evaluators"

        # If evaluatorConfigs is specified, use that (new field with weights)
        # Otherwise, fall back to evaluatorRefs (old field without weights)
        if (
            hasattr(evaluation_set, "evaluator_configs")
            and evaluation_set.evaluator_configs
        ):
            # Use new evaluatorConfigs field - supports weights
            evaluator_ref_ids = {ref.ref for ref in evaluation_set.evaluator_configs}
        else:
            # Fall back to old evaluatorRefs field - plain strings
            evaluator_ref_ids = set(evaluation_set.evaluator_refs)

        found_evaluator_ids = set()

        for file in evaluators_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in evaluator file '{file}': {str(e)}. "
                    f"Please check the file for syntax errors."
                ) from e

            try:
                evaluator_id = data.get("id")
                if evaluator_id in evaluator_ref_ids:
                    evaluator = EvaluatorFactory.create_evaluator(
                        data, evaluators_dir, agent_model=agent_model
                    )
                    evaluators.append(evaluator)
                    found_evaluator_ids.add(evaluator_id)
            except Exception as e:
                raise ValueError(
                    f"Failed to create evaluator from file '{file}': {str(e)}. "
                    f"Please verify the evaluator configuration."
                ) from e

        missing_evaluators = evaluator_ref_ids - found_evaluator_ids
        if missing_evaluators:
            raise ValueError(
                f"Could not find the following evaluators: {missing_evaluators}"
            )

        return evaluators
