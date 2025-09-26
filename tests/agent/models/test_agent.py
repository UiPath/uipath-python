from pydantic import TypeAdapter

from uipath.agent.models.agent import (
    AgentDefinition,
    AgentResourceType,
    AgentUnknownResourceConfig,
    LowCodeAgentDefinition,
    UnknownAgentDefinition,
)


class TestAgentBuilderConfig:
    def test_agent_config_loads_complete_json(self):
        """Test that AgentConfig can load from the complete JSON example with all resource types"""

        json_data = {
            "type": "lowCode",
            "features": [],
            "id": "0e2201f2-b983-42c6-8231-64806c09ae54",
            "inputSchema": {
                "properties": {"inputProp": {"type": "string"}},
                "type": "object",
            },
            "messages": [
                {"content": "You're a helpful agent.", "role": "system"},
                {
                    "content": "Use the provided tools. This is the input argument: {{inputProp}}",
                    "role": "user",
                },
            ],
            "name": "Agent",
            "outputSchema": {
                "properties": {
                    "content": {"description": "Output content", "type": "string"}
                },
                "type": "object",
            },
            "resources": [
                {
                    "$resourceType": "escalation",
                    "channels": [
                        {
                            "id": "Channel id",
                            "description": "Channel description",
                            "inputSchema": {"properties": {}, "type": "object"},
                            "name": "Channel",
                            "outcomeMapping": {"Submit": "continue"},
                            "outputSchema": {
                                "properties": {
                                    "Content": {
                                        "description": "Text content related to the escalation prompt",
                                        "type": "string",
                                    }
                                },
                                "required": ["Content"],
                                "type": "object",
                            },
                            "properties": {
                                "appName": "Untitled",
                                "appVersion": 1,
                                "folderName": None,
                                "resourceKey": "c0aa40e2-9f14-4cea-83f9-c874e229986f",
                            },
                            "recipients": [
                                {
                                    "type": 1,
                                    "value": "e314e6a1-2499-4ff4-af0b-bb81dc29a6ec",
                                }
                            ],
                            "type": "ActionCenter",
                        }
                    ],
                    "description": '"escalation prompt"',
                    "id": "2841bace-fa75-4503-9ff0-dff2c1f68750",
                    "isAgentMemoryEnabled": False,
                    "name": "Escalation_1",
                },
                {
                    "$resourceType": "tool",
                    "arguments": {},
                    "description": "this is an agent package",
                    "inputSchema": {"properties": {}, "type": "object"},
                    "name": "Agent tool",
                    "outputSchema": {
                        "properties": {"output": {"type": "string"}},
                        "type": "object",
                    },
                    "properties": {
                        "folderPath": "Solution Folder",
                        "processName": "Cristi-Basic-Agent",
                    },
                    "settings": {"maxAttempts": 0, "retryDelay": 0, "timeout": 0},
                    "type": "Agent",
                },
                {
                    "$resourceType": "tool",
                    "arguments": {},
                    "description": "Creates an appointment given: first name, second name, personal unique number, doctor specialist, cabinet number, datetime.\nReturns the appointment ID",
                    "guardrail": {
                        "policies": [
                            {
                                "action": {
                                    "$actionType": "log",
                                    "severityLevel": "Info",
                                },
                                "description": "test",
                                "enabledForEvals": True,
                                "name": "Guardrail_1",
                                "rules": [
                                    {"$ruleType": "always", "applyTo": "InputAndOutput"}
                                ],
                            }
                        ]
                    },
                    "inputSchema": {
                        "properties": {
                            "cabinet_number": {"type": "integer"},
                            "datetime": {"type": "string"},
                            "doctor_specialist": {"type": "string"},
                            "first_name": {"type": "string"},
                            "personal_unique_number": {"type": "string"},
                            "second_name": {"type": "string"},
                        },
                        "required": [],
                        "type": "object",
                    },
                    "name": "Process tool with a guardrail",
                    "outputSchema": {
                        "properties": {"appointment_id": {"type": "integer"}},
                        "required": [],
                        "type": "object",
                    },
                    "properties": {
                        "folderPath": "Solution Folder",
                        "processName": "Add_Appointment",
                    },
                    "settings": {"maxAttempts": 0, "retryDelay": 0, "timeout": 0},
                    "type": "Process",
                },
                {
                    "$resourceType": "tool",
                    "arguments": {},
                    "description": "Extract readable text from a publicly accessible URL and provide it in a structured format.",
                    "inputSchema": {
                        "additionalProperties": False,
                        "properties": {
                            "provider": {
                                "description": "The search engine to use.",
                                "enum": ["Jina"],
                                "title": "Search Engine",
                                "type": "string",
                            },
                            "url": {
                                "description": "A publicly accessible URL",
                                "title": "URL",
                                "type": "string",
                            },
                        },
                        "required": ["provider", "url"],
                        "type": "object",
                    },
                    "name": "IS tool",
                    "outputSchema": {"properties": {}, "type": "object"},
                    "properties": {
                        "connection": {
                            "apiBaseUri": "https://alpha.uipath.com/adminstudiotest/cicd/elements_",
                            "connector": {
                                "enabled": True,
                                "image": "https://alpha.uipath.com/elements_/scaleunit_/3854d037-4ab5-4881-909b-968c433f6d88/v3/element/elements/uipath-uipath-airdk/image",
                                "key": "uipath-uipath-airdk",
                                "name": "UiPath GenAI Activities",
                            },
                            "elementInstanceId": 180169,
                            "folder": {
                                "key": "eb6e6ba2-f2ae-4603-b10d-ab101f0ba91f",
                                "path": "Agents Test",
                            },
                            "id": "1c5b8b0a-03ed-4cd2-bfe5-9c3a4341443d",
                            "isDefault": False,
                            "name": "andrei.neculaesei@uipath.com #2",
                            "solutionProperties": {
                                "folder": {
                                    "fullyQualifiedName": "Solution Folder",
                                    "path": "e02827d6-1426-4bfb-13e9-08dd9dd1a5a3",
                                },
                                "resourceKey": "449e43cf-4663-4c44-98c3-5e1a52bd36a3",
                            },
                            "state": "Enabled",
                        },
                        "method": "POST",
                        "objectName": "v1::webRead",
                        "parameters": [
                            {
                                "description": "The search engine to use.",
                                "displayName": "Search Engine",
                                "dynamic": False,
                                "dynamicBehavior": [],
                                "enumValues": [{"name": "Jina", "value": "Jina"}],
                                "fieldLocation": "body",
                                "fieldVariant": "static",
                                "loadReferenceOptionsByDefault": None,
                                "name": "provider",
                                "position": "primary",
                                "reference": None,
                                "required": True,
                                "sortOrder": 1,
                                "type": "string",
                                "value": "Jina",
                            },
                            {
                                "description": "A publicly accessible URL",
                                "displayName": "URL",
                                "dynamic": True,
                                "dynamicBehavior": [],
                                "enumValues": None,
                                "fieldLocation": "body",
                                "fieldVariant": "dynamic",
                                "loadReferenceOptionsByDefault": None,
                                "name": "url",
                                "position": "primary",
                                "reference": None,
                                "required": True,
                                "sortOrder": 2,
                                "type": "string",
                            },
                        ],
                        "toolDescription": "Extract readable text from a publicly accessible URL and provide it in a structured format.",
                        "toolDisplayName": "Web Reader",
                        "toolPath": "/v1/webRead",
                    },
                    "settings": {"maxAttempts": 0, "retryDelay": 0, "timeout": 0},
                    "type": "Integration",
                },
                {
                    "$resourceType": "context",
                    "description": "",
                    "folderPath": "Solution Folder",
                    "indexName": "Medical Index",
                    "name": "Medical Index Semantic",
                    "settings": {
                        "resultCount": 3,
                        "retrievalMode": "Semantic",
                        "threshold": 0,
                    },
                },
                {
                    "$resourceType": "context",
                    "description": "",
                    "folderPath": "Solution Folder",
                    "indexName": "Medical Index",
                    "name": "Medical Index Structured",
                    "settings": {
                        "resultCount": 3,
                        "retrievalMode": "Structured",
                        "threshold": 0,
                    },
                },
            ],
            "settings": {
                "engine": "basic-v1",
                "maxTokens": 16384,
                "model": "gpt-4o-2024-11-20",
                "temperature": 0,
            },
            "version": "1.0.0",
        }

        # Test that the model loads without errors
        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        # Basic assertions
        assert isinstance(config, LowCodeAgentDefinition), (
            "AgentConfig should be a low code agent."
        )
        assert config.id == "0e2201f2-b983-42c6-8231-64806c09ae54"
        assert config.name == "Agent"
        assert config.version == "1.0.0"
        assert len(config.messages) == 2
        assert len(config.resources) == 6  # 1 escalation + 3 tools + 2 context
        assert config.settings.engine == "basic-v1"
        assert config.settings.max_tokens == 16384

        # Validate resource types
        resource_types = [resource.resource_type for resource in config.resources]
        assert resource_types.count(AgentResourceType.ESCALATION) == 1
        assert resource_types.count(AgentResourceType.TOOL) == 3
        assert resource_types.count(AgentResourceType.CONTEXT) == 2

        # Validate specific resources
        escalation_resource = next(
            r
            for r in config.resources
            if r.resource_type == AgentResourceType.ESCALATION
        )
        assert escalation_resource.name == "Escalation_1"

        tool_resources = [
            r for r in config.resources if r.resource_type == AgentResourceType.TOOL
        ]
        tool_names = [t.name for t in tool_resources]
        assert "Agent tool" in tool_names
        assert "Process tool with a guardrail" in tool_names
        assert "IS tool" in tool_names

        context_resources = [
            r for r in config.resources if r.resource_type == AgentResourceType.CONTEXT
        ]
        context_names = [c.name for c in context_resources]
        assert "Medical Index Semantic" in context_names
        assert "Medical Index Structured" in context_names

    def test_agent_config_loads_unknown_resource_json(self):
        """Test that AgentConfig can load JSON with an unknown resource type"""

        json_data = {
            "type": "lowCode",
            "id": "b2564199-e479-4b6f-9336-dc50f457afda",
            "version": "1.0.0",
            "name": "Agent",
            "metadata": {
                "storageVersion": "19.0.0",
                "isConversational": False,
            },
            "messages": [
                {"role": "system", "content": "You are an agentic assistant."},
                {"role": "user", "content": "Search the code..."},
            ],
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Output content"}
                },
            },
            "settings": {
                "model": "gpt-4o-2024-11-20",
                "maxTokens": 16384,
                "temperature": 0,
                "engine": "basic-v1",
            },
            "resources": [
                {
                    "$resourceType": "unknownType",
                    "id": "84250efc-8eb3-471c-8e01-437068dfc464",
                    "name": "mystery_resource",
                    "description": "Some new resource we don't know about",
                    "slug": "mystery-resource",
                    "folderPath": "Solution Folder",
                    "extraField": {"foo": "bar"},
                }
            ],
        }

        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        # Basic assertions
        assert isinstance(config, LowCodeAgentDefinition), (
            "AgentConfig should be a low code agent."
        )
        assert config.id == "b2564199-e479-4b6f-9336-dc50f457afda"
        assert config.name == "Agent"
        assert config.version == "1.0.0"
        assert config.settings.engine == "basic-v1"
        assert config.settings.max_tokens == 16384

        # Validate resources
        assert len(config.resources) == 1
        resource = config.resources[0]

        # Should fall back to AgentUnknownResourceConfig
        assert isinstance(resource, AgentUnknownResourceConfig)
        assert resource.resource_type == "unknownType"
        assert resource.name == "mystery_resource"
        assert resource.extraField == {"foo": "bar"}  # type: ignore[attr-defined]
        assert resource.slug == "mystery-resource"  # type: ignore[attr-defined]

    def test_agent_config_loads_unknown_agent_type(self):
        """Test that AgentConfig can load JSON with an unknown resource type"""

        json_data = {
            "type": "unknownType",
            "id": "b2564199-e479-4b6f-9336-dc50f457afda",
            "version": "1.0.0",
            "name": "Agent",
            "metadata": {
                "storageVersion": "19.0.0",
                "isConversational": False,
            },
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Output content"}
                },
            },
            "resources": [],
        }

        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        # Basic assertions
        assert isinstance(config, UnknownAgentDefinition), (
            "AgentConfig should be an unknown type."
        )
        assert config.id == "b2564199-e479-4b6f-9336-dc50f457afda"
        assert config.name == "Agent"
        assert config.version == "1.0.0"

        # Validate resources
        assert len(config.resources) == 0
