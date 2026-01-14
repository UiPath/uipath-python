"""End-to-end tests for input overrides functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from uipath._cli._evals._models._evaluation_set import (
    EvaluationSet,
    LegacyEvaluationSet,
)
from uipath._cli._evals._runtime import UiPathEvalContext
from uipath._cli._utils._eval_set import EvalHelpers


@pytest.mark.asyncio
async def test_input_overrides_e2e_direct_override():
    """E2E test: per-evaluation input overrides on calculator inputs."""
    # Create a calculator agent.json
    agent_config = {
        "id": "test-calc-agent",
        "version": "1.0.0",
        "name": "Test Calculator",
        "messages": [
            {"role": "system", "content": "You are a calculator."},
            {"role": "user", "content": "Calculate: {{a}} {{operator}} {{b}}"},
        ],
        "inputSchema": {
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
                "operator": {"type": "string"},
            },
        },
        "outputSchema": {
            "type": "object",
            "properties": {"result": {"type": "number"}},
        },
        "settings": {"model": "gpt-4", "temperature": 0},
    }

    # Create evaluation set with inputs that will be overridden
    eval_set = {
        "fileName": "test-eval.json",
        "id": "test-eval-set-id",
        "name": "Test Eval Set",
        "batchSize": 10,
        "evaluatorRefs": [],
        "evaluations": [
            {
                "id": "test-eval-1",
                "name": "Test Override",
                "inputs": {"a": 5, "b": 3, "operator": "+"},
                "expectedOutput": {"result": 50},  # Expect 10 * 5 = 50
                "expectedAgentBehavior": "Should calculate with overridden values",
                "evalSetId": "test-eval-set-id",
                "createdAt": "2025-12-16T00:00:00.000Z",
                "updatedAt": "2025-12-16T00:00:00.000Z",
            }
        ],
        "modelSettings": [],
        "createdAt": "2025-12-16T00:00:00.000Z",
        "updatedAt": "2025-12-16T00:00:00.000Z",
    }

    # Create temp files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write agent.json
        agent_file = tmpdir_path / "agent.json"
        with open(agent_file, "w") as f:
            json.dump(agent_config, f)

        # Write eval set
        eval_file = tmpdir_path / "eval-set.json"
        with open(eval_file, "w") as f:
            json.dump(eval_set, f)

        # Load evaluation set to verify override structure
        loaded_eval_set, _ = EvalHelpers.load_eval_set(str(eval_file))
        assert isinstance(loaded_eval_set, (LegacyEvaluationSet, EvaluationSet))
        assert len(loaded_eval_set.evaluations) == 1
        original_input = loaded_eval_set.evaluations[0].inputs
        assert original_input["a"] == 5
        assert original_input["b"] == 3
        assert original_input["operator"] == "+"

        # Per-evaluation overrides
        overrides = {
            "test-eval-1": {
                "a": 10,
                "operator": "*",
            }
        }

        # Apply overrides to the inputs with eval_id
        from uipath._cli._evals._eval_util import apply_input_overrides

        modified_inputs = apply_input_overrides(
            original_input, overrides, eval_id="test-eval-1"
        )

        # Verify overrides were applied
        assert modified_inputs["a"] == 10  # Overridden
        assert modified_inputs["operator"] == "*"  # Overridden
        assert modified_inputs["b"] == 3  # Unchanged


@pytest.mark.asyncio
async def test_input_overrides_e2e_direct_field():
    """E2E test: input overrides with direct field override."""
    # Create evaluation set
    eval_set = {
        "fileName": "test-eval.json",
        "id": "test-eval-set-id",
        "name": "Test Eval Set",
        "batchSize": 10,
        "evaluatorRefs": [],
        "evaluations": [
            {
                "id": "test-eval-1",
                "name": "Test Direct Field Override",
                "inputs": {
                    "file_id": "old-attachment-123",
                    "document_id": "old-doc-456",
                    "count": 5,
                },
                "expectedOutput": {"status": "success"},
                "expectedAgentBehavior": "Process with new values",
                "evalSetId": "test-eval-set-id",
                "createdAt": "2025-12-16T00:00:00.000Z",
                "updatedAt": "2025-12-16T00:00:00.000Z",
            }
        ],
        "modelSettings": [],
        "createdAt": "2025-12-16T00:00:00.000Z",
        "updatedAt": "2025-12-16T00:00:00.000Z",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write eval set
        eval_file = tmpdir_path / "eval-set.json"
        with open(eval_file, "w") as f:
            json.dump(eval_set, f)

        # Load and test
        loaded_eval_set, _ = EvalHelpers.load_eval_set(str(eval_file))
        original_input = loaded_eval_set.evaluations[0].inputs

        # Per-evaluation overrides
        overrides = {
            "test-eval-1": {
                "file_id": "new-attachment-789",
                "document_id": "new-doc-999",
                "count": 10,
            }
        }

        from uipath._cli._evals._eval_util import apply_input_overrides

        modified_inputs = apply_input_overrides(
            original_input, overrides, eval_id="test-eval-1"
        )

        # Verify direct field override worked
        assert modified_inputs["file_id"] == "new-attachment-789"
        assert modified_inputs["document_id"] == "new-doc-999"
        assert modified_inputs["count"] == 10


@pytest.mark.asyncio
async def test_input_overrides_e2e_nested_objects():
    """E2E test: input overrides with nested objects using deep merge."""
    eval_set = {
        "fileName": "test-eval.json",
        "id": "test-eval-set-id",
        "name": "Test Eval Set",
        "batchSize": 10,
        "evaluatorRefs": [],
        "evaluations": [
            {
                "id": "test-eval-1",
                "name": "Test Nested Override",
                "inputs": {
                    "filePath": {
                        "ID": "old-attachment-id",
                        "FullName": "document.pdf",
                        "MimeType": "application/pdf",
                    },
                    "config": {"threshold": 0.8, "model": "gpt-4"},
                },
                "expectedOutput": {"status": "processed"},
                "expectedAgentBehavior": "Process with overridden attachment",
                "evalSetId": "test-eval-set-id",
                "createdAt": "2025-12-16T00:00:00.000Z",
                "updatedAt": "2025-12-16T00:00:00.000Z",
            }
        ],
        "modelSettings": [],
        "createdAt": "2025-12-16T00:00:00.000Z",
        "updatedAt": "2025-12-16T00:00:00.000Z",
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        eval_file = tmpdir_path / "eval-set.json"
        with open(eval_file, "w") as f:
            json.dump(eval_set, f)

        loaded_eval_set, _ = EvalHelpers.load_eval_set(str(eval_file))
        original_input = loaded_eval_set.evaluations[0].inputs

        # Per-evaluation overrides with deep merge for nested objects
        overrides = {
            "test-eval-1": {
                "filePath": {"ID": "new-attachment-id-xyz"},
                "config": {"threshold": 0.95},
            }
        }

        from uipath._cli._evals._eval_util import apply_input_overrides

        modified_inputs = apply_input_overrides(
            original_input, overrides, eval_id="test-eval-1"
        )

        # Verify deep merge - overridden fields updated, others preserved
        assert (
            modified_inputs["filePath"]["ID"] == "new-attachment-id-xyz"
        )  # Overridden
        assert modified_inputs["filePath"]["FullName"] == "document.pdf"  # Preserved
        assert modified_inputs["filePath"]["MimeType"] == "application/pdf"  # Preserved
        assert modified_inputs["config"]["threshold"] == 0.95  # Overridden
        assert modified_inputs["config"]["model"] == "gpt-4"  # Preserved


@pytest.mark.asyncio
async def test_input_overrides_context_field():
    """Test that UiPathEvalContext properly stores input_overrides."""
    context = UiPathEvalContext()
    context.input_overrides = {"eval-1": {"a": 10, "operator": "*"}}

    assert context.input_overrides is not None
    assert "eval-1" in context.input_overrides
    assert context.input_overrides["eval-1"]["a"] == 10
    assert context.input_overrides["eval-1"]["operator"] == "*"


@pytest.mark.asyncio
async def test_input_overrides_per_evaluation():
    """E2E test: per-evaluation input overrides."""
    # Per-evaluation overrides
    overrides = {
        "eval-1": {"operator": "*", "a": 10},
        "eval-2": {"operator": "/", "b": 5},
    }

    from uipath._cli._evals._eval_util import apply_input_overrides

    # Test eval-1
    eval_1_inputs = {"a": 5, "b": 3, "operator": "+"}
    modified_inputs_1 = apply_input_overrides(
        eval_1_inputs, overrides, eval_id="eval-1"
    )
    assert modified_inputs_1["a"] == 10  # Overridden
    assert modified_inputs_1["operator"] == "*"  # Overridden
    assert modified_inputs_1["b"] == 3  # Preserved

    # Test eval-2
    eval_2_inputs = {"a": 20, "b": 10, "operator": "+"}
    modified_inputs_2 = apply_input_overrides(
        eval_2_inputs, overrides, eval_id="eval-2"
    )
    assert modified_inputs_2["a"] == 20  # Preserved
    assert modified_inputs_2["b"] == 5  # Overridden
    assert modified_inputs_2["operator"] == "/"  # Overridden

    # Test eval-3 (no overrides)
    eval_3_inputs = {"a": 7, "b": 4, "operator": "-"}
    modified_inputs_3 = apply_input_overrides(
        eval_3_inputs, overrides, eval_id="eval-3"
    )
    assert modified_inputs_3["a"] == 7  # Unchanged
    assert modified_inputs_3["b"] == 4  # Unchanged
    assert modified_inputs_3["operator"] == "-"  # Unchanged
