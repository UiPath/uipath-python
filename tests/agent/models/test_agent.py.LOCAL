from pydantic import TypeAdapter

from uipath.agent.models.agent import (
    AgentEscalationResourceConfig,
    AgentMcpResourceConfig,
    AgentResourceType,
    LowCodeAgentDefinition,
    UnknownAgentDefinition,
)


class TestAgentBuilderConfig:
    def test_agent_config_loads_unknown_agent_type(self):
        """Test that AgentDefinition can load JSON with an unknown resource type"""

        json_data = {
            "type": "unknownType",
            "id": "b2564199-e479-4b6f-9336-dc50f457afda",
            "version": "1.0.0",
            "name": "Agent",
            "metadata": {
                "storageVersion": "19.0.0",
                "isConversational": False,
            },
            "messages": [
                {"role": "system", "content": "You are an agentic assistant."},
            ],
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Output content"}
                },
            },
            "settings": {
                "model": "gpt-5-2025-08-07",
                "maxTokens": 16384,
                "temperature": 0,
                "engine": "basic-v1",
            },
            "resources": [],
        }

        config: UnknownAgentDefinition = TypeAdapter(
            UnknownAgentDefinition
        ).validate_python(json_data)

        # Basic assertions
        assert isinstance(config, UnknownAgentDefinition), (
            "AgentDefinition should be an unknown type."
        )
        config_data = config.model_dump()
        assert config_data["id"] == "b2564199-e479-4b6f-9336-dc50f457afda"
        assert config_data["name"] == "Agent"
        assert config_data["version"] == "1.0.0"

        # Validate resources
        assert len(config_data["resources"]) == 0

    def test_agent_with_all_tool_types_loads(self):
        """Test that AgentDefinition can load a complete agent package with all tool types"""

        json_data = {
            "version": "1.0.0",
            "id": "e0f589ff-469a-44b3-8c5f-085826d8fa55",
            "name": "Agent with All Tools",
            "type": "lowCode",
            "metadata": {"isConversational": False, "storageVersion": "22.0.0"},
            "messages": [
                {"role": "System", "content": "You are an agentic assistant."},
                {
                    "role": "User",
                    "content": "Use the provided tools. Execute {{task}} the number of {{times}}.",
                },
            ],
            "inputSchema": {
                "type": "object",
                "required": ["task"],
                "properties": {"task": {"type": "string"}, "times": {"type": "number"}},
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "task_summary": {
                        "type": "string",
                        "description": "describe the actions you have taken in a concise step by step summary",
                    }
                },
                "title": "Outputs",
                "required": ["task_summary"],
            },
            "settings": {
                "model": "gpt-5-2025-08-07",
                "maxTokens": 16384,
                "temperature": 0,
                "engine": "basic-v1",
            },
            "resources": [
                {
                    "$resourceType": "tool",
                    "type": "ProcessOrchestration",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"in_arg": {"type": "string", "title": "in_arg"}},
                        "required": [],
                    },
                    "outputSchema": {
                        "type": "object",
                        "properties": {
                            "out_arg": {"type": "string", "title": "out_arg"}
                        },
                        "required": [],
                    },
                    "arguments": {},
                    "settings": {"timeout": 0, "maxAttempts": 0, "retryDelay": 0},
                    "properties": {
                        "processName": "Basic.Agentic.Process.with.In.and.Out.Arguments",
                        "folderPath": "TestFolder/Complete Solution 30 Sept",
                    },
                    "name": "Maestro Workflow",
                    "description": "agentic process to be invoked by the agent",
                },
                {
                    "$resourceType": "escalation",
                    "id": "be506447-2cf1-47e6-a124-2930e6f0f3d8",
                    "channels": [
                        {
                            "name": "Channel",
                            "description": "Channel description",
                            "type": "ActionCenter",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "AgentName": {"type": "string"},
                                    "Statement": {"type": "string"},
                                },
                                "required": ["AgentName", "Statement"],
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {"Reason": {"type": "string"}},
                            },
                            "outcomeMapping": {
                                "Approve": "continue",
                                "Reject": "continue",
                            },
                            "properties": {
                                "appName": "AgentQuestionApp",
                                "appVersion": 1,
                                "folderName": "TestFolder/Complete Solution 30 Sept",
                                "resourceKey": "b2ecb40b-dcce-4f71-96ae-8fa895905ae2",
                                "isActionableMessageEnabled": True,
                                "actionableMessageMetaData": {
                                    "fieldSet": {
                                        "type": "fieldSet",
                                        "id": "3705cfbb-d1fb-4567-b1dd-036107c5c084",
                                        "fields": [
                                            {
                                                "id": "AgentName",
                                                "name": "AgentName",
                                                "type": "Fact",
                                                "placeHolderText": "",
                                            },
                                            {
                                                "id": "Statement",
                                                "name": "Statement",
                                                "type": "Fact",
                                                "placeHolderText": "",
                                            },
                                            {
                                                "id": "Reason",
                                                "name": "Reason",
                                                "type": "Input.Text",
                                                "placeHolderText": "",
                                            },
                                        ],
                                    },
                                    "actionSet": {
                                        "type": "actionSet",
                                        "id": "9ecd2de3-7ac3-47a6-836c-af1eaf67f9ca",
                                        "actions": [
                                            {
                                                "id": "Approve",
                                                "name": "Approve",
                                                "title": "Approve",
                                                "type": "Action.Http",
                                                "isPrimary": True,
                                            },
                                            {
                                                "id": "Reject",
                                                "name": "Reject",
                                                "title": "Reject",
                                                "type": "Action.Http",
                                                "isPrimary": True,
                                            },
                                        ],
                                    },
                                },
                            },
                            "recipients": [
                                {
                                    "value": "a26a9809-69ee-427a-9f05-ba00623fef80",
                                    "type": "UserId",
                                }
                            ],
                            "taskTitle": "Test Task",
                            "priority": "Medium",
                            "labels": ["new", "stuff"],
                        }
                    ],
                    "isAgentMemoryEnabled": True,
                    "escalationType": 0,
                    "name": "Human in the Loop App",
                    "description": "an app for the agent to ask questions for the human",
                },
                {
                    "$resourceType": "context",
                    "folderPath": "TestFolder",
                    "indexName": "MCP Documentation Index",
                    "settings": {
                        "threshold": 0,
                        "resultCount": 3,
                        "retrievalMode": "Semantic",
                        "query": {
                            "description": "The query for the Semantic strategy.",
                            "variant": "Dynamic",
                        },
                        "folderPathPrefix": {},
                        "fileExtension": {"value": "All"},
                    },
                    "name": "MCP Documentation Index",
                    "description": "",
                },
                {
                    "$resourceType": "tool",
                    "id": "13b3928e-fad8-4bc1-ac06-31718143ded1",
                    "referenceKey": "b54f2c33-40ee-4dda-b662-b6f787bc1ede",
                    "name": "Basic RPA Process",
                    "type": "process",
                    "description": "RPA process to execute a given task",
                    "location": "external",
                    "isEnabled": True,
                    "inputSchema": {
                        "type": "object",
                        "properties": {"task": {"type": "string"}},
                        "required": ["task"],
                    },
                    "outputSchema": {
                        "type": "object",
                        "properties": {"output": {"type": "string"}},
                    },
                    "settings": {},
                    "properties": {
                        "processName": "Basic RPA Process",
                        "folderPath": "TestFolder/Complete Solution 30 Sept",
                    },
                },
                {
                    "$resourceType": "tool",
                    "type": "Api",
                    "inputSchema": {"type": "object", "properties": {}},
                    "outputSchema": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean"},
                            "summary": {"type": "string"},
                        },
                        "title": "Outputs",
                        "required": ["success", "summary"],
                    },
                    "arguments": {},
                    "settings": {"timeout": 0, "maxAttempts": 0, "retryDelay": 0},
                    "properties": {
                        "processName": "Basic Http and Log API Wf",
                        "folderPath": "TestFolder/Complete Solution 30 Sept",
                    },
                    "name": "Basic Http and Log API Wf",
                    "description": "api workflow to be invoked by agent",
                },
                {
                    "$resourceType": "mcp",
                    "folderPath": "TestFolder/Complete Solution 30 Sept",
                    "slug": "time-mcp",
                    "availableTools": [
                        {
                            "name": "get_current_time",
                            "description": "Get current time in a specific timezones",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "timezone": {
                                        "type": "string",
                                        "description": "IANA timezone name (e.g., 'America/New_York', 'Europe/London'). Use 'UTC' as local timezone if no timezone provided by the user.",
                                    }
                                },
                                "required": ["timezone"],
                            },
                        },
                        {
                            "name": "convert_time",
                            "description": "Convert time between timezones",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "source_timezone": {
                                        "type": "string",
                                        "description": "Source IANA timezone name (e.g., 'America/New_York', 'Europe/London'). Use 'UTC' as local timezone if no source timezone provided by the user.",
                                    },
                                    "time": {
                                        "type": "string",
                                        "description": "Time to convert in 24-hour format (HH:MM)",
                                    },
                                    "target_timezone": {
                                        "type": "string",
                                        "description": "Target IANA timezone name (e.g., 'Asia/Tokyo', 'America/San_Francisco'). Use 'UTC' as local timezone if no target timezone provided by the user.",
                                    },
                                },
                                "required": [
                                    "source_timezone",
                                    "time",
                                    "target_timezone",
                                ],
                            },
                        },
                    ],
                    "name": "time_mcp",
                    "description": "mcp server to get the current time",
                },
                {
                    "$resourceType": "tool",
                    "type": "Agent",
                    "inputSchema": {"type": "object", "properties": {}},
                    "outputSchema": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Output content",
                            }
                        },
                    },
                    "arguments": {},
                    "settings": {"timeout": 0, "maxAttempts": 0, "retryDelay": 0},
                    "properties": {
                        "processName": "Current Date Agent",
                        "folderPath": "TestFolder/Complete Solution 30 Sept",
                    },
                    "name": "Current Date Agent",
                    "description": "subagent to be invoked by agent",
                },
            ],
            "features": [],
        }

        # Test that the model loads without errors
        config: LowCodeAgentDefinition = TypeAdapter(
            LowCodeAgentDefinition
        ).validate_python(json_data)

        # Basic assertions
        assert isinstance(config, LowCodeAgentDefinition), (
            "AgentDefinition should be a low code agent."
        )
        assert config.id == "e0f589ff-469a-44b3-8c5f-085826d8fa55"
        assert config.name == "Agent with All Tools"
        assert config.version == "1.0.0"
        assert len(config.messages) == 2
        assert len(config.resources) == 7  # All tool types + escalation + context + mcp
        assert config.settings.engine == "basic-v1"
        assert config.settings.max_tokens == 16384

        # Validate resource types
        resource_types = [resource.resource_type for resource in config.resources]
        assert resource_types.count(AgentResourceType.ESCALATION) == 1
        assert resource_types.count(AgentResourceType.TOOL) == 4
        assert resource_types.count(AgentResourceType.CONTEXT) == 1
        assert resource_types.count(AgentResourceType.MCP) == 1

        # Validate tool types (ProcessOrchestration, Process, Api, Agent)
        tool_resources = [
            r for r in config.resources if r.resource_type == AgentResourceType.TOOL
        ]
        assert len(tool_resources) == 4

        tool_names = [t.name for t in tool_resources]
        assert "Maestro Workflow" in tool_names  # ProcessOrchestration
        assert "Basic RPA Process" in tool_names  # Process
        assert "Basic Http and Log API Wf" in tool_names  # Api
        assert "Current Date Agent" in tool_names  # Agent

        # Validate MCP resource
        mcp_resources = [
            r for r in config.resources if r.resource_type == AgentResourceType.MCP
        ]
        assert len(mcp_resources) == 1
        mcp_resource = mcp_resources[0]
        assert isinstance(mcp_resource, AgentMcpResourceConfig)
        assert mcp_resource.name == "time_mcp"
        assert mcp_resource.slug == "time-mcp"
        assert len(mcp_resource.available_tools) == 2
        assert mcp_resource.available_tools[0].name == "get_current_time"
        assert mcp_resource.available_tools[1].name == "convert_time"

        # Validate escalation resource with detailed properties
        escalation_resource = next(
            r
            for r in config.resources
            if r.resource_type == AgentResourceType.ESCALATION
        )
        assert isinstance(escalation_resource, AgentEscalationResourceConfig)
        assert escalation_resource.name == "Human in the Loop App"
        assert escalation_resource.is_agent_memory_enabled is True
        assert len(escalation_resource.channels) == 1
        channel = escalation_resource.channels[0]
        assert channel.name == "Channel"
        assert channel.task_title == "Test Task"
        assert channel.priority == "Medium"
        assert channel.labels == ["new", "stuff"]

        # Validate context resource
        context_resources = [
            r for r in config.resources if r.resource_type == AgentResourceType.CONTEXT
        ]
        assert len(context_resources) == 1
        assert context_resources[0].name == "MCP Documentation Index"
