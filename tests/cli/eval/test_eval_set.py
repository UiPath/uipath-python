"""Tests for evaluation set loading and migration functions."""

import json
import tempfile
from pathlib import Path

import pytest

from uipath._cli._evals._models._evaluation_set import (
    EvaluationSet,
)
from uipath._cli._evals.mocks.types import LLMMockingStrategy
from uipath._cli._utils._eval_set import EvalHelpers


@pytest.mark.asyncio
async def test_migrate_evaluation_item_with_empty_simulation_instructions():
    """Test that migration supports empty simulation_instructions.

    This test verifies the fix that allows LLMMockingStrategy to be created
    even when simulation_instructions is None or empty, as long as
    simulate_tools is True.
    """
    # Create a legacy evaluation set with simulate_tools=True but
    # simulation_instructions is None (empty)
    legacy_eval_set = {
        "fileName": "test-eval.json",
        "id": "test-eval-set-id",
        "name": "Test Eval Set",
        "batchSize": 10,
        "evaluatorRefs": ["evaluator1"],
        "evaluations": [
            {
                "id": "test-eval-1",
                "name": "Test Empty Simulation Instructions",
                "inputs": {"test": "value"},
                "expectedOutput": {"result": "success"},
                "expectedAgentBehavior": "Should handle empty simulation",
                "evalSetId": "test-eval-set-id",
                "createdAt": "2025-01-26T00:00:00.000Z",
                "updatedAt": "2025-01-26T00:00:00.000Z",
                "simulateTools": True,
                "simulationInstructions": None,  # Empty instructions
                "toolsToSimulate": [],
            }
        ],
        "modelSettings": [],
        "createdAt": "2025-01-26T00:00:00.000Z",
        "updatedAt": "2025-01-26T00:00:00.000Z",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        eval_file = tmpdir_path / "eval-set.json"
        with open(eval_file, "w") as f:
            json.dump(legacy_eval_set, f)

        # Load the evaluation set
        loaded_eval_set, _ = EvalHelpers.load_eval_set(str(eval_file))

        # Verify it was migrated to EvaluationSet (not LegacyEvaluationSet)
        assert isinstance(loaded_eval_set, EvaluationSet)
        assert len(loaded_eval_set.evaluations) == 1

        evaluation = loaded_eval_set.evaluations[0]

        # The key assertion: mocking_strategy should be created despite
        # empty simulation_instructions
        assert evaluation.mocking_strategy is not None
        assert isinstance(evaluation.mocking_strategy, LLMMockingStrategy)

        # Verify the strategy has an empty prompt (not None)
        assert evaluation.mocking_strategy.prompt == ""
        assert evaluation.mocking_strategy.tools_to_simulate == []


@pytest.mark.asyncio
async def test_migrate_evaluation_item_with_simulation_instructions():
    """Test migration with non-empty simulation instructions."""
    legacy_eval_set = {
        "fileName": "test-eval.json",
        "id": "test-eval-set-id",
        "name": "Test Eval Set",
        "batchSize": 10,
        "evaluatorRefs": ["evaluator1"],
        "evaluations": [
            {
                "id": "test-eval-1",
                "name": "Test With Simulation Instructions",
                "inputs": {"test": "value"},
                "expectedOutput": {"result": "success"},
                "expectedAgentBehavior": "Should use provided instructions",
                "evalSetId": "test-eval-set-id",
                "createdAt": "2025-01-26T00:00:00.000Z",
                "updatedAt": "2025-01-26T00:00:00.000Z",
                "simulateTools": True,
                "simulationInstructions": "Mock the API calls",
                "toolsToSimulate": [{"name": "api_call"}],
            }
        ],
        "modelSettings": [],
        "createdAt": "2025-01-26T00:00:00.000Z",
        "updatedAt": "2025-01-26T00:00:00.000Z",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        eval_file = tmpdir_path / "eval-set.json"
        with open(eval_file, "w") as f:
            json.dump(legacy_eval_set, f)

        loaded_eval_set, _ = EvalHelpers.load_eval_set(str(eval_file))

        assert isinstance(loaded_eval_set, EvaluationSet)
        assert len(loaded_eval_set.evaluations) == 1

        evaluation = loaded_eval_set.evaluations[0]

        # Verify the strategy was created with the provided instructions
        assert evaluation.mocking_strategy is not None
        assert isinstance(evaluation.mocking_strategy, LLMMockingStrategy)
        assert evaluation.mocking_strategy.prompt == "Mock the API calls"
        assert len(evaluation.mocking_strategy.tools_to_simulate) == 1
        assert evaluation.mocking_strategy.tools_to_simulate[0].name == "api_call"


@pytest.mark.asyncio
async def test_migrate_evaluation_item_without_simulate_tools():
    """Test that no mocking_strategy is created when simulate_tools is False/None."""
    legacy_eval_set = {
        "fileName": "test-eval.json",
        "id": "test-eval-set-id",
        "name": "Test Eval Set",
        "batchSize": 10,
        "evaluatorRefs": ["evaluator1"],
        "evaluations": [
            {
                "id": "test-eval-1",
                "name": "Test Without Tool Simulation",
                "inputs": {"test": "value"},
                "expectedOutput": {"result": "success"},
                "expectedAgentBehavior": "No tool simulation",
                "evalSetId": "test-eval-set-id",
                "createdAt": "2025-01-26T00:00:00.000Z",
                "updatedAt": "2025-01-26T00:00:00.000Z",
                "simulateTools": False,
                "simulationInstructions": "Mock the API calls",
            }
        ],
        "modelSettings": [],
        "createdAt": "2025-01-26T00:00:00.000Z",
        "updatedAt": "2025-01-26T00:00:00.000Z",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        eval_file = tmpdir_path / "eval-set.json"
        with open(eval_file, "w") as f:
            json.dump(legacy_eval_set, f)

        loaded_eval_set, _ = EvalHelpers.load_eval_set(str(eval_file))

        assert isinstance(loaded_eval_set, EvaluationSet)
        assert len(loaded_eval_set.evaluations) == 1

        evaluation = loaded_eval_set.evaluations[0]

        # When simulate_tools is False, no mocking_strategy should be created
        assert evaluation.mocking_strategy is None


@pytest.mark.asyncio
async def test_migrate_evaluation_item_with_input_mocking():
    """Test migration with input mocking strategy."""
    legacy_eval_set = {
        "fileName": "test-eval.json",
        "id": "test-eval-set-id",
        "name": "Test Eval Set",
        "batchSize": 10,
        "evaluatorRefs": ["evaluator1"],
        "evaluations": [
            {
                "id": "test-eval-1",
                "name": "Test With Input Mocking",
                "inputs": {"test": "value"},
                "expectedOutput": {"result": "success"},
                "expectedAgentBehavior": "Should have input mocking",
                "evalSetId": "test-eval-set-id",
                "createdAt": "2025-01-26T00:00:00.000Z",
                "updatedAt": "2025-01-26T00:00:00.000Z",
                "simulateInput": True,
                "inputGenerationInstructions": "Generate test inputs",
                "simulateTools": True,
                "simulationInstructions": None,
            }
        ],
        "modelSettings": [],
        "createdAt": "2025-01-26T00:00:00.000Z",
        "updatedAt": "2025-01-26T00:00:00.000Z",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        eval_file = tmpdir_path / "eval-set.json"
        with open(eval_file, "w") as f:
            json.dump(legacy_eval_set, f)

        loaded_eval_set, _ = EvalHelpers.load_eval_set(str(eval_file))

        assert isinstance(loaded_eval_set, EvaluationSet)
        assert len(loaded_eval_set.evaluations) == 1

        evaluation = loaded_eval_set.evaluations[0]

        # Both strategies should be present
        assert evaluation.input_mocking_strategy is not None
        assert evaluation.input_mocking_strategy.prompt == "Generate test inputs"

        assert evaluation.mocking_strategy is not None
        assert isinstance(evaluation.mocking_strategy, LLMMockingStrategy)
        assert evaluation.mocking_strategy.prompt == ""
