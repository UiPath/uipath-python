"""Tests for agent memory settings in evaluation sets and the eval CLI override."""

import json
import tempfile
from pathlib import Path

from uipath._cli.cli_eval import _resolve_agent_memory_settings_override
from uipath.eval.helpers import EvalHelpers
from uipath.eval.models.evaluation_set import (
    EvaluationSet,
    EvaluationSetAgentMemorySettings,
)


def make_eval_set(**overrides) -> EvaluationSet:
    data = {
        "id": "eval-set-1",
        "name": "Test Eval Set",
        "version": "1.0",
        "evaluatorConfigs": [],
        "evaluations": [],
        **overrides,
    }
    return EvaluationSet.model_validate(data)


class TestEvaluationSetSchema:
    def test_parses_agent_memory_fields(self):
        eval_set = make_eval_set(
            agentMemoryEnabled=True,
            agentMemorySettings=[
                {
                    "id": "primary-memory",
                    "resultCount": "5",
                    "searchMode": "hybrid",
                    "threshold": "0.8",
                }
            ],
        )

        assert eval_set.agent_memory_enabled is True
        assert len(eval_set.agent_memory_settings) == 1
        setting = eval_set.agent_memory_settings[0]
        assert setting.id == "primary-memory"
        assert setting.result_count == "5"
        assert setting.search_mode == "hybrid"
        assert setting.threshold == "0.8"

    def test_defaults_preserve_existing_eval_sets(self):
        eval_set = make_eval_set()

        assert eval_set.agent_memory_enabled is False
        assert eval_set.agent_memory_settings == []

    def test_memory_settings_default_to_same_as_agent(self):
        setting = EvaluationSetAgentMemorySettings(id="s1")

        assert setting.result_count == "same-as-agent"
        assert setting.search_mode == "same-as-agent"
        assert setting.threshold == "same-as-agent"

    def test_serializes_with_camel_case_aliases(self):
        eval_set = make_eval_set(
            agentMemoryEnabled=True,
            agentMemorySettings=[{"id": "s1", "searchMode": "semantic"}],
        )

        dumped = eval_set.model_dump(by_alias=True)
        assert dumped["agentMemoryEnabled"] is True
        assert dumped["agentMemorySettings"][0]["searchMode"] == "semantic"


class TestLegacyEvalSetMigration:
    def test_legacy_migration_preserves_agent_memory_fields(self):
        legacy_eval_set = {
            "fileName": "test-eval.json",
            "id": "test-eval-set-id",
            "name": "Test Eval Set",
            "batchSize": 10,
            "evaluatorRefs": ["evaluator1"],
            "evaluations": [],
            "modelSettings": [],
            "agentMemoryEnabled": True,
            "agentMemorySettings": [
                {
                    "id": "primary-memory",
                    "resultCount": "5",
                    "searchMode": "hybrid",
                    "threshold": "0.8",
                }
            ],
            "createdAt": "2025-01-26T00:00:00.000Z",
            "updatedAt": "2025-01-26T00:00:00.000Z",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            eval_file = Path(tmpdir) / "eval-set.json"
            eval_file.write_text(json.dumps(legacy_eval_set))

            loaded_eval_set, _ = EvalHelpers.load_eval_set(str(eval_file))

        assert loaded_eval_set.agent_memory_enabled is True
        assert len(loaded_eval_set.agent_memory_settings) == 1
        assert loaded_eval_set.agent_memory_settings[0].id == "primary-memory"


class TestResolveAgentMemorySettingsOverride:
    def test_memory_disabled_returns_disabled_override(self):
        eval_set = make_eval_set(agentMemoryEnabled=False)

        override = _resolve_agent_memory_settings_override("default", eval_set)

        assert override == {"enabled": False}

    def test_memory_enabled_default_id_uses_first_setting(self):
        eval_set = make_eval_set(
            agentMemoryEnabled=True,
            agentMemorySettings=[
                {
                    "id": "s1",
                    "resultCount": "5",
                    "searchMode": "hybrid",
                    "threshold": "0.8",
                },
                {
                    "id": "s2",
                    "resultCount": "10",
                    "searchMode": "semantic",
                    "threshold": "0.5",
                },
            ],
        )

        override = _resolve_agent_memory_settings_override("default", eval_set)

        assert override == {
            "enabled": True,
            "resultCount": "5",
            "searchMode": "hybrid",
            "threshold": "0.8",
        }

    def test_memory_enabled_selects_setting_by_id(self):
        eval_set = make_eval_set(
            agentMemoryEnabled=True,
            agentMemorySettings=[
                {"id": "s1", "searchMode": "hybrid"},
                {
                    "id": "s2",
                    "resultCount": "10",
                    "searchMode": "semantic",
                    "threshold": "0.5",
                },
            ],
        )

        override = _resolve_agent_memory_settings_override("s2", eval_set)

        assert override == {
            "enabled": True,
            "resultCount": "10",
            "searchMode": "semantic",
            "threshold": "0.5",
        }

    def test_default_id_matches_persisted_default_entry(self):
        # The eval-set editor persists a "default" entry (all same-as-agent)
        # alongside user-defined settings; it may not be first in the list.
        eval_set = make_eval_set(
            agentMemoryEnabled=True,
            agentMemorySettings=[
                {
                    "id": "s1",
                    "resultCount": "10",
                    "searchMode": "semantic",
                    "threshold": "0.5",
                },
                {"id": "default"},
            ],
        )

        override = _resolve_agent_memory_settings_override("default", eval_set)

        assert override == {
            "enabled": True,
            "resultCount": "same-as-agent",
            "searchMode": "same-as-agent",
            "threshold": "same-as-agent",
        }

    def test_unknown_id_falls_back_to_first_setting(self):
        eval_set = make_eval_set(
            agentMemoryEnabled=True,
            agentMemorySettings=[{"id": "s1", "searchMode": "hybrid"}],
        )

        override = _resolve_agent_memory_settings_override("missing", eval_set)

        assert override["enabled"] is True
        assert override["searchMode"] == "hybrid"

    def test_memory_enabled_without_settings_keeps_agent_configuration(self):
        eval_set = make_eval_set(agentMemoryEnabled=True)

        override = _resolve_agent_memory_settings_override("default", eval_set)

        assert override == {"enabled": True}
