"""Tests for load_agent_definition function from uipath.agent.utils._utils."""

import json
import tempfile
from pathlib import Path

import pytest

from uipath.agent.models.evals import AgentEvalsDefinition
from uipath.agent.utils._utils import load_agent_definition


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestLoadAgentDefinition:
    """Test suite for load_agent_definition function."""

    def test_load_agent_definition_with_legacy_evaluators(self, temp_project_dir):
        """Test loading agent definition with legacy evaluators."""
        # Create agent.json
        agent_data = {
            "id": "test-agent-1",
            "name": "Test Agent",
            "version": "1.0.0",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Help the user."},
            ],
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
            },
            "settings": {
                "model": "gpt-4o",
                "maxTokens": 2048,
                "temperature": 0.7,
                "engine": "basic-v1",
            },
        }

        with open(temp_project_dir / "agent.json", "w") as f:
            json.dump(agent_data, f)

        # Create evaluators directory with a legacy evaluator
        evals_dir = temp_project_dir / "evaluations" / "evaluators"
        evals_dir.mkdir(parents=True, exist_ok=True)

        legacy_evaluator = {
            "fileName": "evaluator-default.json",
            "id": "legacy-eval-1",
            "name": "Default Evaluator",
            "description": "An LLM-based evaluator",
            "category": 1,  # LlmAsAJudge
            "type": 5,
            "prompt": "Evaluate the output.",
            "model": "same-as-agent",
            "targetOutputKey": "*",
            "createdAt": "2025-02-04T00:00:00.000Z",
            "updatedAt": "2025-02-04T00:00:00.000Z",
        }

        with open(evals_dir / "evaluator-default.json", "w") as f:
            json.dump(legacy_evaluator, f)

        # Create eval-sets directory (empty)
        eval_sets_dir = temp_project_dir / "evaluations" / "eval-sets"
        eval_sets_dir.mkdir(parents=True, exist_ok=True)

        # Load and validate
        result = load_agent_definition(temp_project_dir)

        assert isinstance(result, AgentEvalsDefinition)
        assert result.id == "test-agent-1"
        assert result.name == "Test Agent"
        assert result.version == "1.0.0"
        # Evaluators should be loaded
        assert len(result.evaluators or []) == 1
        evaluator = (result.evaluators or [])[0]
        assert evaluator.id == "legacy-eval-1"

    def test_load_agent_definition_with_coded_evaluators(self, temp_project_dir):
        """Test loading agent definition with non-legacy (coded) evaluators."""
        # Create agent.json
        agent_data = {
            "id": "test-agent-2",
            "name": "Test Agent with Coded Evaluators",
            "version": "1.0.0",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Help the user."},
            ],
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
            },
            "settings": {
                "model": "gpt-4o",
                "maxTokens": 2048,
                "temperature": 0.7,
                "engine": "basic-v1",
            },
        }

        with open(temp_project_dir / "agent.json", "w") as f:
            json.dump(agent_data, f)

        # Create evaluators directory with a coded evaluator (ExactMatchEvaluator)
        evals_dir = temp_project_dir / "evaluations" / "evaluators"
        evals_dir.mkdir(parents=True, exist_ok=True)

        coded_evaluator = {
            "version": "1.0",
            "id": "exact-match-eval",
            "description": "Checks if the response exactly matches the expected value.",
            "evaluatorTypeId": "uipath-exact-match",
            "evaluatorConfig": {
                "name": "ExactMatchEvaluator",
                "targetOutputKey": "*",
                "negated": False,
                "caseSensitive": False,
                "defaultEvaluationCriteria": {"expectedOutput": "expected response"},
            },
        }

        with open(evals_dir / "exact-match.json", "w") as f:
            json.dump(coded_evaluator, f)

        # Create eval-sets directory (empty)
        eval_sets_dir = temp_project_dir / "evaluations" / "eval-sets"
        eval_sets_dir.mkdir(parents=True, exist_ok=True)

        # Load and validate
        result = load_agent_definition(temp_project_dir)

        assert isinstance(result, AgentEvalsDefinition)
        assert result.id == "test-agent-2"
        assert result.name == "Test Agent with Coded Evaluators"
        # Evaluators should be loaded
        assert len(result.evaluators or []) == 1
        evaluator = (result.evaluators or [])[0]
        assert evaluator.id == "exact-match-eval"

    def test_load_agent_definition_with_mixed_evaluators(self, temp_project_dir):
        """Test loading agent definition with both legacy and coded evaluators."""
        # Create agent.json
        agent_data = {
            "id": "test-agent-3",
            "name": "Test Agent with Mixed Evaluators",
            "version": "1.0.0",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Help the user."},
            ],
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
            },
            "settings": {
                "model": "gpt-4o",
                "maxTokens": 2048,
                "temperature": 0.7,
                "engine": "basic-v1",
            },
        }

        with open(temp_project_dir / "agent.json", "w") as f:
            json.dump(agent_data, f)

        # Create evaluators directory with both legacy and coded evaluators
        evals_dir = temp_project_dir / "evaluations" / "evaluators"
        evals_dir.mkdir(parents=True, exist_ok=True)

        # Legacy evaluator
        legacy_evaluator = {
            "fileName": "evaluator-legacy.json",
            "id": "legacy-eval",
            "name": "Legacy Evaluator",
            "category": 1,
            "type": 5,
            "prompt": "Evaluate the output.",
            "model": "same-as-agent",
            "targetOutputKey": "*",
            "createdAt": "2025-02-04T00:00:00.000Z",
            "updatedAt": "2025-02-04T00:00:00.000Z",
        }

        with open(evals_dir / "legacy.json", "w") as f:
            json.dump(legacy_evaluator, f)

        # Coded evaluator
        coded_evaluator = {
            "version": "1.0",
            "id": "exact-match-eval",
            "description": "Exact match evaluator",
            "evaluatorTypeId": "uipath-exact-match",
            "evaluatorConfig": {
                "name": "ExactMatchEvaluator",
                "targetOutputKey": "*",
                "negated": False,
                "caseSensitive": False,
                "defaultEvaluationCriteria": {"expectedOutput": "expected"},
            },
        }

        with open(evals_dir / "exact-match.json", "w") as f:
            json.dump(coded_evaluator, f)

        # Create eval-sets directory (empty)
        eval_sets_dir = temp_project_dir / "evaluations" / "eval-sets"
        eval_sets_dir.mkdir(parents=True, exist_ok=True)

        # Load and validate
        result = load_agent_definition(temp_project_dir)

        assert isinstance(result, AgentEvalsDefinition)
        assert result.id == "test-agent-3"
        assert len(result.evaluators or []) == 2

        # Verify both evaluators are present
        evaluator_ids = [e.id for e in (result.evaluators or [])]
        assert "legacy-eval" in evaluator_ids
        assert "exact-match-eval" in evaluator_ids

    def test_load_agent_definition_with_evaluator_and_resources(self, temp_project_dir):
        """Test loading agent definition with coded evaluator and agent.json resources."""
        # Create agent.json with resources
        agent_data = {
            "id": "test-agent-4",
            "name": "Agent with Evaluator and Resources",
            "version": "1.0.0",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
            ],
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
            },
            "settings": {
                "model": "gpt-4o",
                "maxTokens": 2048,
                "temperature": 0.7,
                "engine": "basic-v1",
            },
        }

        with open(temp_project_dir / "agent.json", "w") as f:
            json.dump(agent_data, f)

        # Create evaluators directory with a coded evaluator
        evals_dir = temp_project_dir / "evaluations" / "evaluators"
        evals_dir.mkdir(parents=True, exist_ok=True)

        coded_evaluator = {
            "version": "1.0",
            "id": "exact-match-eval-4",
            "description": "Exact match evaluator",
            "evaluatorTypeId": "uipath-exact-match",
            "evaluatorConfig": {
                "name": "ExactMatchEvaluator",
                "targetOutputKey": "*",
                "negated": False,
                "caseSensitive": False,
                "defaultEvaluationCriteria": {"expectedOutput": "expected"},
            },
        }

        with open(evals_dir / "exact-match.json", "w") as f:
            json.dump(coded_evaluator, f)

        # Create eval-sets directory (empty)
        eval_sets_dir = temp_project_dir / "evaluations" / "eval-sets"
        eval_sets_dir.mkdir(parents=True, exist_ok=True)

        # Load and validate
        result = load_agent_definition(temp_project_dir)

        assert isinstance(result, AgentEvalsDefinition)
        assert result.id == "test-agent-4"
        assert len(result.evaluators or []) == 1
        evaluator = (result.evaluators or [])[0]
        assert evaluator.id == "exact-match-eval-4"

    def test_load_agent_definition_missing_evaluators_directory(self, temp_project_dir):
        """Test loading agent definition when evaluators directory doesn't exist."""
        # Create agent.json
        agent_data = {
            "id": "test-agent-5",
            "name": "Agent without Evaluators Dir",
            "version": "1.0.0",
            "messages": [
                {"role": "system", "content": "You are helpful."},
            ],
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
            },
            "settings": {
                "model": "gpt-4o",
                "maxTokens": 2048,
                "temperature": 0.7,
                "engine": "basic-v1",
            },
        }

        with open(temp_project_dir / "agent.json", "w") as f:
            json.dump(agent_data, f)

        # Don't create evaluators or eval-sets directories

        # Load and validate - should handle missing directories gracefully
        result = load_agent_definition(temp_project_dir)

        assert isinstance(result, AgentEvalsDefinition)
        assert result.id == "test-agent-5"
        assert result.evaluators is None or len(result.evaluators or []) == 0
        assert result.evaluation_sets is None or len(result.evaluation_sets or []) == 0


class TestLoadAgentDefinitionErrors:
    """Error path tests for load_agent_definition."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_missing_agent_json_raises(self, temp_project_dir):
        """Loading from a directory without agent.json raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_agent_definition(temp_project_dir)

    def test_malformed_json_in_agent_file_raises(self, temp_project_dir):
        """Invalid JSON in agent.json raises json.JSONDecodeError."""
        agent_file = temp_project_dir / "agent.json"
        agent_file.write_text("{ not valid json !!!")

        with pytest.raises(json.JSONDecodeError):
            load_agent_definition(temp_project_dir)

    @pytest.mark.parametrize(
        "subdir,filename",
        [
            ("resources", "bad_resource.json"),
            ("evaluations/evaluators", "broken.json"),
        ],
        ids=["malformed-resource", "malformed-evaluator"],
    )
    def test_malformed_sidecar_file_is_skipped(
        self, temp_project_dir, subdir, filename
    ):
        """Malformed JSON in resources/ or evaluators/ is skipped, not fatal."""
        agent_data = {
            "id": "test-malformed",
            "name": "Agent with bad sidecar file",
            "version": "1.0.0",
            "messages": [{"role": "system", "content": "hi"}],
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {"type": "object", "properties": {}},
            "settings": {
                "model": "gpt-4o",
                "maxTokens": 2048,
                "temperature": 0.7,
                "engine": "basic-v1",
            },
        }

        with open(temp_project_dir / "agent.json", "w") as f:
            json.dump(agent_data, f)

        target_dir = temp_project_dir / subdir
        target_dir.mkdir(parents=True)
        (target_dir / filename).write_text("NOT JSON AT ALL")

        # Also create eval-sets if testing evaluators (required sibling dir)
        if "evaluations" in subdir:
            (temp_project_dir / "evaluations" / "eval-sets").mkdir(
                parents=True, exist_ok=True
            )

        result = load_agent_definition(temp_project_dir)
        assert result.id == "test-malformed"
