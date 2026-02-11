"""Tests for legacy AgentDefinition backwards compatibility."""

import copy

from pydantic import TypeAdapter

from uipath.agent.models._legacy import normalize_legacy_format
from uipath.agent.models.agent import (
    AgentDefinition,
    AgentResourceType,
)
from uipath.agent.models.evals import AgentEvalsDefinition

_MINIMAL_SETTINGS = {
    "engine": "basic-v1",
    "model": "gpt-4o",
    "maxTokens": 4096,
    "temperature": 0,
}

_MINIMAL_SCHEMAS = {
    "inputSchema": {"type": "object", "properties": {}},
    "outputSchema": {"type": "object", "properties": {}},
}


def _base(**overrides):
    """Return a minimal modern-format dict, with overrides merged in."""
    d = {
        "version": "1.0.0",
        "settings": _MINIMAL_SETTINGS,
        **_MINIMAL_SCHEMAS,
    }
    d.update(overrides)
    return d


class TestNormalizeLegacyFormatMessages:
    def test_modern_format_passes_through_unchanged(self):
        data = _base(
            messages=[
                {"role": "system", "content": "hello"},
                {"role": "user", "content": "world"},
            ],
            resources=[],
        )
        original = copy.deepcopy(data)
        normalize_legacy_format(data)
        assert data["messages"] == original["messages"]
        assert data["resources"] == original["resources"]

    def test_system_and_user_prompt_strings(self):
        data = _base(systemPrompt="sys", userPrompt="usr")
        normalize_legacy_format(data)
        assert len(data["messages"]) == 2
        assert data["messages"][0] == {"role": "system", "content": "sys"}
        assert data["messages"][1] == {"role": "user", "content": "usr"}
        assert "systemPrompt" not in data
        assert "userPrompt" not in data

    def test_system_prompt_only(self):
        data = _base(systemPrompt={"content": "sys only"})
        normalize_legacy_format(data)
        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "system"
        assert data["messages"][0]["content"] == "sys only"

    def test_user_prompt_only(self):
        data = _base(userPrompt={"content": "usr only"})
        normalize_legacy_format(data)
        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "usr only"

    def test_prompts_as_dicts(self):
        data = _base(
            systemPrompt={"content": "sys dict"},
            userPrompt={"content": "usr dict"},
        )
        normalize_legacy_format(data)
        assert data["messages"][0] == {"role": "system", "content": "sys dict"}
        assert data["messages"][1] == {"role": "user", "content": "usr dict"}

    def test_existing_messages_not_overwritten(self):
        data = _base(
            messages=[{"role": "system", "content": "keep me"}],
            systemPrompt={"content": "should be ignored"},
            userPrompt={"content": "should also be ignored"},
        )
        normalize_legacy_format(data)
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "keep me"
        # legacy fields still cleaned up
        assert "systemPrompt" not in data
        assert "userPrompt" not in data


class TestNormalizeLegacyFormatResources:
    def test_tools_become_tool_resources(self):
        tool = {
            "name": "t1",
            "description": "d1",
            "type": "Process",
            "inputSchema": {},
            "outputSchema": {},
            "properties": {},
            "settings": {},
        }
        data = _base(tools=[tool])
        normalize_legacy_format(data)
        assert len(data["resources"]) == 1
        assert data["resources"][0]["$resourceType"] == "tool"
        assert data["resources"][0]["isEnabled"] is True
        assert "tools" not in data

    def test_contexts_become_context_resources(self):
        ctx = {
            "name": "c1",
            "description": "d1",
            "folderPath": "f",
            "indexName": "i",
            "settings": {"resultCount": 3, "retrievalMode": "Semantic"},
        }
        data = _base(contexts=[ctx])
        normalize_legacy_format(data)
        assert len(data["resources"]) == 1
        assert data["resources"][0]["$resourceType"] == "context"
        assert "contexts" not in data

    def test_escalations_become_escalation_resources(self):
        esc = {"name": "e1", "description": "d1", "channels": [], "escalationType": 0}
        data = _base(escalations=[esc])
        normalize_legacy_format(data)
        assert len(data["resources"]) == 1
        assert data["resources"][0]["$resourceType"] == "escalation"
        assert "escalations" not in data

    def test_mixed_legacy_resources_maintain_order(self):
        tool = {"name": "t", "description": "d"}
        ctx = {"name": "c", "description": "d"}
        esc = {"name": "e", "description": "d"}
        data = _base(tools=[tool], contexts=[ctx], escalations=[esc])
        normalize_legacy_format(data)
        types = [r["$resourceType"] for r in data["resources"]]
        assert types == ["tool", "context", "escalation"]

    def test_existing_resources_not_overwritten(self):
        data = _base(
            resources=[{"$resourceType": "tool", "name": "keep"}],
            tools=[{"name": "ignored", "description": "d"}],
        )
        normalize_legacy_format(data)
        assert len(data["resources"]) == 1
        assert data["resources"][0]["name"] == "keep"

    def test_setdefault_does_not_overwrite_existing_resource_type(self):
        tool = {"name": "t", "description": "d", "$resourceType": "custom"}
        data = _base(tools=[tool])
        normalize_legacy_format(data)
        assert data["resources"][0]["$resourceType"] == "custom"


class TestNormalizeLegacyFormatCleanup:
    def test_legacy_fields_removed(self):
        data = _base(
            systemPrompt={"content": "s"},
            userPrompt={"content": "u"},
            tools=[],
            contexts=[],
            escalations=[],
        )
        normalize_legacy_format(data)
        legacy_fields = [
            "systemPrompt",
            "userPrompt",
            "tools",
            "contexts",
            "escalations",
        ]
        for key in legacy_fields:
            assert key not in data


class TestNormalizeLegacyFormatIdempotent:
    def test_double_application_is_stable(self):
        data = _base(
            systemPrompt={"content": "sys"},
            userPrompt={"content": "usr"},
            tools=[{"name": "t", "description": "d"}],
        )
        normalize_legacy_format(data)
        snapshot = copy.deepcopy(data)
        normalize_legacy_format(data)
        assert data == snapshot


class TestLegacyAgentDefinitionIntegration:
    def _legacy_payload(self, **extra):
        """Build a complete legacy payload that should parse into AgentDefinition."""
        payload = {
            "version": "1.0.0",
            "settings": _MINIMAL_SETTINGS,
            **_MINIMAL_SCHEMAS,
            "systemPrompt": {"content": "You are an assistant."},
            "userPrompt": {"content": "Help with {{task}}."},
        }
        payload.update(extra)
        return payload

    def test_basic_legacy_payload_parses(self):
        data = self._legacy_payload()
        agent = TypeAdapter(AgentDefinition).validate_python(data)
        assert len(agent.messages) == 2
        assert agent.messages[0].role == "system"
        assert agent.messages[0].content == "You are an assistant."
        assert agent.messages[1].role == "user"
        assert agent.messages[1].content == "Help with {{task}}."

    def test_legacy_payload_with_all_resource_types(self):
        data = self._legacy_payload(
            tools=[
                {
                    "name": "MyTool",
                    "description": "A process tool",
                    "type": "Process",
                    "inputSchema": {"type": "object", "properties": {}},
                    "outputSchema": {"type": "object", "properties": {}},
                    "properties": {"folderPath": "f", "processName": "p"},
                    "settings": {"maxAttempts": 0, "retryDelay": 0, "timeout": 0},
                }
            ],
            contexts=[
                {
                    "name": "MyContext",
                    "description": "A context",
                    "folderPath": "f",
                    "indexName": "idx",
                    "settings": {
                        "resultCount": 5,
                        "retrievalMode": "Semantic",
                        "threshold": 0,
                    },
                }
            ],
            escalations=[
                {
                    "name": "MyEscalation",
                    "description": "An escalation",
                    "escalationType": 0,
                    "channels": [
                        {
                            "name": "ch",
                            "type": "ActionCenter",
                            "description": "chan desc",
                            "inputSchema": {"type": "object", "properties": {}},
                            "outputSchema": {"type": "object", "properties": {}},
                            "properties": {"appVersion": 1},
                            "recipients": [{"type": "UserId", "value": "uid"}],
                        }
                    ],
                }
            ],
        )

        agent = TypeAdapter(AgentDefinition).validate_python(data)

        assert len(agent.messages) == 2
        assert len(agent.resources) == 3

        types = [r.resource_type for r in agent.resources]
        assert AgentResourceType.TOOL in types
        assert AgentResourceType.CONTEXT in types
        assert AgentResourceType.ESCALATION in types

    def test_legacy_format_through_evals_definition(self):
        data = {
            "version": "1.0.0",
            "settings": _MINIMAL_SETTINGS,
            **_MINIMAL_SCHEMAS,
            "systemPrompt": {"content": "Eval agent prompt"},
            "userPrompt": {"content": "Eval user prompt"},
            "tools": [
                {
                    "name": "EvalTool",
                    "description": "Tool for eval",
                    "type": "Process",
                    "inputSchema": {"type": "object", "properties": {}},
                    "outputSchema": {"type": "object", "properties": {}},
                    "properties": {"folderPath": "f", "processName": "p"},
                    "settings": {"maxAttempts": 0, "retryDelay": 0, "timeout": 0},
                }
            ],
        }

        agent = TypeAdapter(AgentEvalsDefinition).validate_python(data)

        assert isinstance(agent, AgentEvalsDefinition)
        assert len(agent.messages) == 2
        assert agent.messages[0].content == "Eval agent prompt"
        assert len(agent.resources) == 1
        assert agent.resources[0].resource_type == AgentResourceType.TOOL
