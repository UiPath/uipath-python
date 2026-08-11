"""Tests for the ``AgentExecution`` -> ``WorkloadExecution`` rename (v2.12.0).

Covers the soft-deprecated class-name shim, the intentional hard break on the
renamed model fields, and the positional-dispatch contract that keeps custom
evaluators using the old ``agent_execution`` parameter name working.
"""

import importlib
import uuid

import pytest
from pydantic import ValidationError

from uipath.eval.evaluators.exact_match_evaluator import ExactMatchEvaluator
from uipath.eval.models import NumericEvaluationResult, WorkloadExecution


@pytest.mark.parametrize(
    "module_path",
    ["uipath.eval.models", "uipath.eval.models.models"],
)
def test_agent_execution_alias_warns_and_resolves(module_path: str) -> None:
    """Accessing the legacy ``AgentExecution`` name warns and returns the new class."""
    module = importlib.import_module(module_path)

    with pytest.warns(DeprecationWarning, match="AgentExecution is deprecated"):
        legacy = module.AgentExecution

    assert legacy is WorkloadExecution


@pytest.mark.parametrize(
    "module_path",
    ["uipath.eval.models", "uipath.eval.models.models"],
)
def test_unknown_attribute_raises(module_path: str) -> None:
    """Unknown attributes still raise ``AttributeError`` via the module ``__getattr__``."""
    module = importlib.import_module(module_path)

    with pytest.raises(AttributeError, match="does_not_exist"):
        _ = module.does_not_exist


def test_old_field_names_are_a_hard_break() -> None:
    """The renamed fields are NOT aliased — old field names raise ValidationError.

    This is the intentional breaking change in v2.12.0 (no field-level back-compat
    shim); only the class *name* is soft-deprecated.
    """
    with pytest.raises(ValidationError):
        WorkloadExecution(
            agent_input={},
            agent_output={"result": "ok"},  # type: ignore[call-arg]
            agent_trace=[],
        )


async def test_old_param_name_still_dispatches_positionally() -> None:
    """A custom evaluator overriding ``evaluate`` with the old ``agent_execution``
    parameter name keeps working, because the base dispatches positionally.
    """

    class CustomEvaluator(ExactMatchEvaluator):
        # Deliberately uses the pre-2.12.0 parameter name.
        async def evaluate(self, agent_execution, evaluation_criteria):
            return await super().evaluate(agent_execution, evaluation_criteria)

    evaluator = CustomEvaluator.model_validate(
        {
            "evaluatorConfig": {"name": "CustomExactMatch", "case_sensitive": True},
            "id": str(uuid.uuid4()),
        }
    )
    workload_execution = WorkloadExecution(
        agent_input={},
        workload_output={"output": "Test output"},
        workload_trace=[],
    )
    raw_criteria = {"expected_output": {"output": "Test output"}}

    # Called positionally (as the runtime does) — must not raise TypeError.
    result = await evaluator.validate_and_evaluate_criteria(
        workload_execution, raw_criteria
    )

    assert isinstance(result, NumericEvaluationResult)
    assert result.score == 1.0
