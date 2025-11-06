from pydantic import TypeAdapter

from uipath.agent.models.agent import (
    AgentBuiltInValidatorGuardrail,
    AgentContextResourceConfig,
    AgentContextRetrievalMode,
    AgentCustomGuardrail,
    AgentDefinition,
    AgentEscalationRecipientType,
    AgentEscalationResourceConfig,
    AgentGuardrailActionType,
    AgentGuardrailBlockAction,
    AgentGuardrailEscalateAction,
    AgentGuardrailUnknownAction,
    AgentIntegrationToolResourceConfig,
    AgentMcpResourceConfig,
    AgentProcessToolResourceConfig,
    AgentResourceType,
    AgentToolType,
    AgentUnknownGuardrail,
    AgentUnknownResourceConfig,
    AgentUnknownToolResourceConfig,
)
from uipath.models.guardrails import (
    EnumListParameterValue,
    MapEnumParameterValue,
    WordRule,
)


class TestAgentBuilderConfig:
    def test_agent_with_all_tool_types_loads(self):
        """Test that AgentDefinition can load a complete agent package with all tool types"""

        json_data = {
            "version": "1.0.0",
            "id": "e0f589ff-469a-44b3-8c5f-085826d8fa55",
            "name": "Agent with All Tools",
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
                    "$guardrailType": "custom",
                    "id": "001",
                    "rules": [{"$ruleType": "always", "applyTo": "inputAndOutput"}],
                    "selector": {"scopes": ["Tool"]},
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
                {
                    "$resourceType": "tool",
                    "type": "Integration",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "To": {"type": "string", "title": "To"},
                            "Subject": {"type": "string", "title": "Subject"},
                        },
                        "required": ["To"],
                    },
                    "outputSchema": {"type": "object", "properties": {}},
                    "arguments": {},
                    "settings": {"timeout": 0, "maxAttempts": 0, "retryDelay": 0},
                    "properties": {
                        "toolPath": "/SendEmail",
                        "objectName": "SendEmail",
                        "toolDisplayName": "Send Email",
                        "toolDescription": "Sends an email message",
                        "method": "POST",
                        "bodyStructure": {
                            "contentType": "multipart",
                            "jsonBodySection": "body",
                        },
                        "connection": {
                            "id": "cccccccc-0000-0000-0000-000000000004",
                            "name": "Gmail Connection",
                            "elementInstanceId": 0,
                            "apiBaseUri": "",
                            "state": "enabled",
                            "isDefault": False,
                            "connector": {
                                "key": "uipath-google-gmail",
                                "name": "Gmail",
                                "enabled": True,
                            },
                            "folder": {"key": "bbbbbbbb-0000-0000-0000-000000000004"},
                            "solutionProperties": {
                                "resourceKey": "cccccccc-0000-0000-0000-000000000004"
                            },
                        },
                        "parameters": [
                            {
                                "name": "To",
                                "displayName": "To",
                                "type": "string",
                                "fieldLocation": "body",
                                "value": "{{prompt}}",
                                "fieldVariant": "dynamic",
                                "sortOrder": 1,
                                "required": True,
                            },
                        ],
                    },
                    "name": "Send Email",
                    "description": "Send an email via Gmail",
                    "isEnabled": True,
                },
            ],
            "features": [],
        }

        # Test that the model loads without errors
        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        # Basic assertions
        assert isinstance(config, AgentDefinition), (
            "AgentDefinition should be a low code agent."
        )
        assert config.id == "e0f589ff-469a-44b3-8c5f-085826d8fa55"
        assert config.name == "Agent with All Tools"
        assert config.version == "1.0.0"
        assert len(config.messages) == 2
        assert len(config.resources) == 8  # All tool types + escalation + context + mcp
        assert config.settings.engine == "basic-v1"
        assert config.settings.max_tokens == 16384

        # Validate resource types
        resource_types = [resource.resource_type for resource in config.resources]
        assert resource_types.count(AgentResourceType.ESCALATION) == 1
        assert resource_types.count(AgentResourceType.TOOL) == 5
        assert resource_types.count(AgentResourceType.CONTEXT) == 1
        assert resource_types.count(AgentResourceType.MCP) == 1

        # Validate tool types (ProcessOrchestration, Process, Api, Agent, Integration)
        tool_resources = [
            r for r in config.resources if r.resource_type == AgentResourceType.TOOL
        ]
        assert len(tool_resources) == 5

        tool_names = [t.name for t in tool_resources]
        assert "Maestro Workflow" in tool_names  # ProcessOrchestration
        assert "Basic RPA Process" in tool_names  # Process
        assert "Basic Http and Log API Wf" in tool_names  # Api
        assert "Current Date Agent" in tool_names  # Agent
        assert "Send Email" in tool_names  # Integration

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

        # Validate Integration tool resource
        integration_tools = [
            r
            for r in config.resources
            if isinstance(r, AgentIntegrationToolResourceConfig)
        ]
        assert len(integration_tools) == 1
        integration_tool = integration_tools[0]
        assert integration_tool.type == AgentToolType.INTEGRATION
        assert integration_tool.name == "Send Email"
        assert integration_tool.properties.tool_path == "/SendEmail"
        assert integration_tool.properties.method == "POST"
        assert integration_tool.properties.connection.connector is not None
        assert (
            integration_tool.properties.connection.connector["key"]
            == "uipath-google-gmail"
        )
        assert integration_tool.properties.body_structure is not None
        assert integration_tool.properties.body_structure["contentType"] == "multipart"
        assert len(integration_tool.properties.parameters) == 1
        assert integration_tool.properties.parameters[0].name == "To"

    def test_agent_config_loads_guardrails(self):
        """Test that AgentConfig can load and parse both Custom and Built-in guardrails from real JSON"""

        json_data = {
            "id": "55f89eb5-e4dc-4129-8c3d-da80f6c7f921",
            "name": "NumberTranslator",
            "version": "1.0.0",
            "settings": {
                "model": "gpt-4o-2024-11-20",
                "maxTokens": 16384,
                "temperature": 0,
                "engine": "basic-v1",
            },
            "inputSchema": {
                "type": "object",
                "required": ["number"],
                "properties": {"number": {"type": "string", "description": "number"}},
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Output content"}
                },
            },
            "metadata": {"storageVersion": "23.0.0", "isConversational": False},
            "resources": [
                {
                    "$resourceType": "tool",
                    "name": "StringToNumber",
                    "description": "Converts word to number",
                    "type": "agent",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"word": {"type": "string"}},
                        "required": ["word"],
                    },
                    "outputSchema": {"type": "object", "properties": {}},
                    "arguments": {},
                    "settings": {"timeout": 0, "maxAttempts": 0, "retryDelay": 0},
                    "properties": {
                        "processName": "StringToNumber",
                        "folderPath": "solution_folder",
                    },
                }
            ],
            "guardrails": [
                {
                    "$guardrailType": "builtInValidator",
                    "id": "2f36abe1-2ae1-457b-b565-ccf7a1b6d088",
                    "name": "PII detection guardrail",
                    "description": "This validator is designed to detect personally identifiable information using Azure Cognitive Services",
                    "validatorType": "pii_detection",
                    "validatorParameters": [
                        {
                            "$parameterType": "enum-list",
                            "id": "entities",
                            "value": ["Email", "Address"],
                        },
                        {
                            "$parameterType": "map-enum",
                            "id": "entityThresholds",
                            "value": {"Email": 1, "Address": 0.7},
                        },
                    ],
                    "action": {
                        "$actionType": "escalate",
                        "app": {
                            "id": "cf4cb73d-7310-49b1-9a9e-e7653dad7f4e",
                            "version": "0",
                            "name": "-Guardrail Form",
                            "folderId": "d0195402-505d-54c1-0b94-5faa5bf69ad1",
                            "folderName": "solution_folder",
                        },
                        "recipient": {
                            "type": 1,
                            "value": "5f872639-fc71-4a50-b17d-f68eb357b436",
                            "displayName": "User Name",
                        },
                    },
                    "enabledForEvals": True,
                    "selector": {"scopes": ["Tool"], "matchNames": ["StringToNumber"]},
                },
                {
                    "$guardrailType": "custom",
                    "id": "7b2a9218-c3d2-4f19-a800-8d6fe77a64e2",
                    "name": "ExcludeHELLO",
                    "description": 'the input shouldn\'t be "hello"',
                    "rules": [
                        {
                            "$ruleType": "word",
                            "fieldSelector": {
                                "$selectorType": "specific",
                                "fields": [{"path": "word", "source": "input"}],
                            },
                            "operator": "doesNotContain",
                            "value": "hello",
                        }
                    ],
                    "action": {"$actionType": "block", "reason": 'Input is "hello"'},
                    "enabledForEvals": True,
                    "selector": {"scopes": ["Tool"], "matchNames": ["StringToNumber"]},
                },
            ],
            "messages": [
                {
                    "role": "system",
                    "content": "You are a English to Romanian translator",
                },
                {
                    "role": "user",
                    "content": "Use the tool StringToNumber to convert the string {{number}} into a number type, then write the obtained number in romanian. ",
                },
            ],
        }

        # Parse with TypeAdapter
        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        # Validate the main agent properties
        assert isinstance(config, AgentDefinition), "Agent should be a AgentDefinition"

        # Validate tool resource type discrimination
        tool_resource = config.resources[0]
        assert isinstance(tool_resource, AgentProcessToolResourceConfig), (
            "Tool should be parsed as AgentProcessToolResourceConfig based on type='Agent'"
        )
        assert tool_resource.resource_type == AgentResourceType.TOOL
        assert tool_resource.type == AgentToolType.AGENT  # The discriminator field

        # Validate agent-level guardrails
        assert config.guardrails is not None
        assert len(config.guardrails) == 2

        # Test built-in validator at agent level
        agent_builtin_guardrail = config.guardrails[0]
        assert isinstance(agent_builtin_guardrail, AgentBuiltInValidatorGuardrail), (
            "Agent guardrail should be AgentBuiltInValidatorGuardrail"
        )

        # Check base guardrail properties
        assert agent_builtin_guardrail.id == "2f36abe1-2ae1-457b-b565-ccf7a1b6d088"
        assert agent_builtin_guardrail.name == "PII detection guardrail"
        assert (
            agent_builtin_guardrail.description
            == "This validator is designed to detect personally identifiable information using Azure Cognitive Services"
        )
        assert agent_builtin_guardrail.enabled_for_evals is True
        assert agent_builtin_guardrail.selector.scopes == ["Tool"]
        assert agent_builtin_guardrail.selector.match_names == ["StringToNumber"]

        # Check built-in validator specific properties
        assert agent_builtin_guardrail.guardrail_type == "builtInValidator"
        assert agent_builtin_guardrail.validator_type == "pii_detection"
        assert len(agent_builtin_guardrail.validator_parameters) == 2

        # Check validator parameters
        enum_param = agent_builtin_guardrail.validator_parameters[0]
        assert isinstance(enum_param, EnumListParameterValue), (
            "Should be EnumListParameterValue based on $parameterType='enum-list'"
        )
        assert enum_param.parameter_type == "enum-list"
        assert enum_param.id == "entities"
        assert enum_param.value == ["Email", "Address"]

        map_param = agent_builtin_guardrail.validator_parameters[1]
        assert isinstance(map_param, MapEnumParameterValue), (
            "Should be MapEnumParameterValue based on $parameterType='map-enum'"
        )
        assert map_param.parameter_type == "map-enum"
        assert map_param.id == "entityThresholds"
        assert map_param.value == {"Email": 1, "Address": 0.7}

        # Check action
        escalate_action = agent_builtin_guardrail.action
        assert isinstance(escalate_action, AgentGuardrailEscalateAction), (
            "Should be EscalateAction based on $actionType='escalate'"
        )
        assert escalate_action.action_type == "escalate"
        assert escalate_action.app.id == "cf4cb73d-7310-49b1-9a9e-e7653dad7f4e"
        assert escalate_action.app.name == "-Guardrail Form"
        assert escalate_action.app.folder_name == "solution_folder"
        assert escalate_action.recipient.type == AgentEscalationRecipientType.USER_ID
        assert escalate_action.recipient.value == "5f872639-fc71-4a50-b17d-f68eb357b436"
        assert escalate_action.recipient.display_name == "User Name"

        # Test custom guardrail at agent level
        agent_custom_guardrail = config.guardrails[1]
        assert isinstance(agent_custom_guardrail, AgentCustomGuardrail), (
            "Agent custom guardrail should be AgentCustomGuardrail"
        )

        # Check base guardrail properties
        assert agent_custom_guardrail.id == "7b2a9218-c3d2-4f19-a800-8d6fe77a64e2"
        assert agent_custom_guardrail.name == "ExcludeHELLO"
        assert agent_custom_guardrail.description == 'the input shouldn\'t be "hello"'
        assert agent_custom_guardrail.enabled_for_evals is True
        assert agent_custom_guardrail.selector.scopes == ["Tool"]
        assert agent_custom_guardrail.selector.match_names == ["StringToNumber"]

        # Check custom guardrail specific properties
        assert agent_custom_guardrail.guardrail_type == "custom"
        assert len(agent_custom_guardrail.rules) == 1

        # Check rule
        rule = agent_custom_guardrail.rules[0]
        assert isinstance(rule, WordRule), (
            "Rule should be WordRule based on $ruleType='word'"
        )
        assert rule.rule_type == "word"
        assert rule.operator == "doesNotContain"  # Updated to use the correct operator
        assert rule.value == "hello"

        # Check field selector
        assert rule.field_selector.selector_type == "specific"
        assert len(rule.field_selector.fields) == 1
        assert rule.field_selector.fields[0].path == "word"
        assert rule.field_selector.fields[0].source == "input"

        # Check action
        block_action = agent_custom_guardrail.action
        assert isinstance(block_action, AgentGuardrailBlockAction), (
            "Should be BlockAction based on $actionType='block'"
        )
        assert block_action.action_type == "block"
        assert block_action.reason == 'Input is "hello"'

    def test_agent_with_gmail_send_email_integration(self):
        """Test agent with Gmail Send Email integration tool"""

        json_data = {
            "version": "1.0.0",
            "id": "aaaaaaaa-0000-0000-0000-000000000001",
            "name": "Agent with Send Email Tool",
            "metadata": {"isConversational": False, "storageVersion": "26.0.0"},
            "messages": [
                {"role": "System", "content": "You are an agentic assistant."},
            ],
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
            },
            "settings": {
                "model": "gpt-4o-2024-11-20",
                "maxTokens": 16384,
                "temperature": 0,
                "engine": "basic-v2",
            },
            "resources": [
                {
                    "$resourceType": "tool",
                    "type": "Integration",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "SaveAsDraft": {
                                "type": "boolean",
                                "title": "Save as draft",
                                "description": "Send an email message. By default, the email will be saved as draft.",
                            },
                            "CC": {
                                "type": "string",
                                "title": "CC",
                                "description": "The secondary recipients of the email, separated by comma (,)",
                            },
                            "Importance": {
                                "type": "string",
                                "title": "Importance",
                                "description": "The importance of the mail",
                                "enum": ["normal"],
                                "oneOf": [
                                    {"const": "normal", "title": "Normal"},
                                    {"const": "high", "title": "High"},
                                    {"const": "low", "title": "Low"},
                                ],
                            },
                            "ReplyTo": {
                                "type": "string",
                                "title": "Reply to",
                                "description": "The email addresses to use when replying, separated by comma (,)",
                            },
                            "BCC": {
                                "type": "string",
                                "title": "BCC",
                                "description": "The hidden recipients of the email, separated by comma (,)",
                            },
                            "To": {
                                "type": "string",
                                "title": "To",
                                "description": "The primary recipients of the email, separated by comma (,)",
                            },
                            "Body": {
                                "type": "string",
                                "title": "Body",
                                "description": "The body of the email",
                            },
                            "Subject": {
                                "type": "string",
                                "title": "Subject",
                                "description": "The subject of the email",
                            },
                        },
                        "additionalProperties": False,
                        "required": ["To"],
                    },
                    "outputSchema": {"type": "object", "properties": {}},
                    "arguments": {},
                    "settings": {"timeout": 0, "maxAttempts": 0, "retryDelay": 0},
                    "properties": {
                        "toolPath": "/SendEmail",
                        "objectName": "SendEmail",
                        "toolDisplayName": "Send Email",
                        "toolDescription": "Sends an email message",
                        "method": "POST",
                        "bodyStructure": {
                            "contentType": "multipart",
                            "jsonBodySection": "body",
                        },
                        "connection": {
                            "id": "cccccccc-0000-0000-0000-000000000001",
                            "name": "Gmail Connection",
                            "elementInstanceId": 0,
                            "apiBaseUri": "",
                            "state": "enabled",
                            "isDefault": False,
                            "connector": {
                                "key": "uipath-google-gmail",
                                "name": "Gmail",
                                "enabled": True,
                            },
                            "folder": {"key": "bbbbbbbb-0000-0000-0000-000000000001"},
                            "solutionProperties": {
                                "resourceKey": "cccccccc-0000-0000-0000-000000000001"
                            },
                        },
                        "parameters": [
                            {
                                "name": "body",
                                "displayName": "Body",
                                "type": "string",
                                "fieldLocation": "multipart",
                                "value": "{{prompt}}",
                                "description": "The message body\n",
                                "position": "primary",
                                "sortOrder": 1,
                                "required": True,
                                "fieldVariant": "dynamic",
                                "dynamic": True,
                                "isCascading": False,
                                "enumValues": None,
                                "loadReferenceOptionsByDefault": None,
                                "dynamicBehavior": [],
                                "reference": None,
                            },
                            {
                                "name": "SaveAsDraft",
                                "displayName": "Save as draft",
                                "type": "boolean",
                                "fieldLocation": "query",
                                "value": False,
                                "description": "",
                                "position": "primary",
                                "sortOrder": 2,
                                "required": False,
                                "fieldVariant": "static",
                                "dynamic": True,
                                "isCascading": False,
                                "enumValues": None,
                                "loadReferenceOptionsByDefault": None,
                                "dynamicBehavior": [],
                                "reference": None,
                            },
                            {
                                "name": "To",
                                "displayName": "To",
                                "type": "string",
                                "fieldLocation": "body",
                                "value": "{{prompt}}",
                                "description": "The primary recipients of the email, separated by comma (,)",
                                "position": "primary",
                                "sortOrder": 3,
                                "required": True,
                                "fieldVariant": "dynamic",
                                "isCascading": False,
                                "dynamic": True,
                                "enumValues": None,
                                "loadReferenceOptionsByDefault": None,
                                "dynamicBehavior": [],
                                "reference": None,
                            },
                            {
                                "name": "Subject",
                                "displayName": "Subject",
                                "type": "string",
                                "fieldLocation": "body",
                                "value": "{{prompt}}",
                                "description": "The subject of the email",
                                "position": "primary",
                                "sortOrder": 4,
                                "required": False,
                                "fieldVariant": "dynamic",
                                "isCascading": False,
                                "dynamic": True,
                                "enumValues": None,
                                "loadReferenceOptionsByDefault": None,
                                "dynamicBehavior": [],
                                "reference": None,
                            },
                            {
                                "name": "Body",
                                "displayName": "Body",
                                "type": "string",
                                "fieldLocation": "body",
                                "value": "{{prompt}}",
                                "description": "The body of the email",
                                "componentType": "RichTextEditorHTML",
                                "position": "primary",
                                "sortOrder": 5,
                                "required": False,
                                "fieldVariant": "dynamic",
                                "isCascading": False,
                                "dynamic": True,
                                "enumValues": None,
                                "loadReferenceOptionsByDefault": None,
                                "dynamicBehavior": [],
                                "reference": None,
                            },
                            {
                                "name": "file",
                                "displayName": "Attachment",
                                "type": "file",
                                "fieldLocation": "multipart",
                                "value": "{{prompt}}",
                                "description": "The attachment to be sent with the email",
                                "position": "primary",
                                "sortOrder": 6,
                                "required": False,
                                "fieldVariant": "dynamic",
                                "dynamic": True,
                                "isCascading": False,
                                "enumValues": None,
                                "loadReferenceOptionsByDefault": None,
                                "dynamicBehavior": [],
                                "reference": None,
                            },
                            {
                                "name": "Importance",
                                "displayName": "Importance",
                                "type": "string",
                                "fieldLocation": "body",
                                "value": "normal",
                                "description": "",
                                "position": "secondary",
                                "sortOrder": 7,
                                "required": False,
                                "fieldVariant": "static",
                                "isCascading": False,
                                "dynamic": True,
                                "enumValues": [
                                    {"name": "Normal", "value": "normal"},
                                    {"name": "High", "value": "high"},
                                    {"name": "Low", "value": "low"},
                                ],
                                "loadReferenceOptionsByDefault": None,
                                "dynamicBehavior": [],
                                "reference": None,
                            },
                            {
                                "name": "ReplyTo",
                                "displayName": "Reply to",
                                "type": "string",
                                "fieldLocation": "body",
                                "value": "{{prompt}}",
                                "description": "The email addresses to use when replying, separated by comma (,)",
                                "position": "secondary",
                                "sortOrder": 8,
                                "required": False,
                                "fieldVariant": "dynamic",
                                "isCascading": False,
                                "dynamic": True,
                                "enumValues": None,
                                "loadReferenceOptionsByDefault": None,
                                "dynamicBehavior": [],
                                "reference": None,
                            },
                            {
                                "name": "CC",
                                "displayName": "CC",
                                "type": "string",
                                "fieldLocation": "body",
                                "value": "{{prompt}}",
                                "description": "The secondary recipients of the email, separated by comma (,)",
                                "position": "secondary",
                                "sortOrder": 9,
                                "required": False,
                                "fieldVariant": "dynamic",
                                "isCascading": False,
                                "dynamic": True,
                                "enumValues": None,
                                "loadReferenceOptionsByDefault": None,
                                "dynamicBehavior": [],
                                "reference": None,
                            },
                            {
                                "name": "BCC",
                                "displayName": "BCC",
                                "type": "string",
                                "fieldLocation": "body",
                                "value": "{{prompt}}",
                                "description": "The hidden recipients of the email, separated by comma (,)",
                                "position": "secondary",
                                "sortOrder": 10,
                                "required": False,
                                "fieldVariant": "dynamic",
                                "isCascading": False,
                                "dynamic": True,
                                "enumValues": None,
                                "loadReferenceOptionsByDefault": None,
                                "dynamicBehavior": [],
                                "reference": None,
                            },
                        ],
                    },
                    "name": "Send Email",
                    "description": "Sends an email message",
                    "isEnabled": True,
                }
            ],
            "features": [],
        }

        # Test deserialization
        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        # Validate agent
        assert config.id == "aaaaaaaa-0000-0000-0000-000000000001"
        assert config.name == "Agent with Send Email Tool"
        assert len(config.resources) == 1

        # Validate integration tool
        tool = config.resources[0]
        assert isinstance(tool, AgentIntegrationToolResourceConfig)
        assert tool.type == AgentToolType.INTEGRATION
        assert tool.name == "Send Email"
        assert tool.description == "Sends an email message"

        # Validate tool properties
        assert tool.properties.tool_path == "/SendEmail"
        assert tool.properties.object_name == "SendEmail"
        assert tool.properties.tool_display_name == "Send Email"
        assert tool.properties.method == "POST"

        # Validate connection
        assert tool.properties.connection is not None
        assert tool.properties.connection.connector is not None
        assert tool.properties.connection.connector["key"] == "uipath-google-gmail"

        # Validate body structure
        assert tool.properties.body_structure is not None
        assert tool.properties.body_structure["contentType"] == "multipart"

        # Validate parameters
        assert len(tool.properties.parameters) == 10
        assert tool.properties.parameters[0].name == "body"
        assert tool.properties.parameters[0].field_location == "multipart"
        assert tool.properties.parameters[0].required is True

        # Validate additional email parameters
        param_names = [p.name for p in tool.properties.parameters]
        assert "Subject" in param_names
        assert "Body" in param_names
        assert "CC" in param_names
        assert "BCC" in param_names
        assert "ReplyTo" in param_names
        assert "Importance" in param_names

        # Validate input_schema properties
        assert tool.input_schema is not None
        assert tool.input_schema["type"] == "object"
        assert "properties" in tool.input_schema
        assert "required" in tool.input_schema
        assert tool.input_schema["required"] == ["To"]
        assert tool.input_schema["additionalProperties"] is False

        # Validate input_schema property fields
        schema_props = tool.input_schema["properties"]
        assert "SaveAsDraft" in schema_props
        assert schema_props["SaveAsDraft"]["type"] == "boolean"
        assert schema_props["SaveAsDraft"]["title"] == "Save as draft"

        assert "To" in schema_props
        assert schema_props["To"]["type"] == "string"
        assert schema_props["To"]["title"] == "To"
        assert "separated by comma" in schema_props["To"]["description"]

        assert "Subject" in schema_props
        assert schema_props["Subject"]["type"] == "string"

        assert "Body" in schema_props
        assert schema_props["Body"]["type"] == "string"
        assert schema_props["Body"]["description"] == "The body of the email"

        assert "CC" in schema_props
        assert schema_props["CC"]["type"] == "string"

        assert "BCC" in schema_props
        assert schema_props["BCC"]["type"] == "string"

        assert "ReplyTo" in schema_props
        assert schema_props["ReplyTo"]["type"] == "string"
        assert schema_props["ReplyTo"]["title"] == "Reply to"

        assert "Importance" in schema_props
        assert schema_props["Importance"]["type"] == "string"
        assert "enum" in schema_props["Importance"]
        assert schema_props["Importance"]["enum"] == ["normal"]
        assert "oneOf" in schema_props["Importance"]
        assert len(schema_props["Importance"]["oneOf"]) == 3

    def test_agent_with_jira_create_issue_integration(self):
        """Test agent with Jira Create Issue (Task) integration tool"""

        json_data = {
            "version": "1.0.0",
            "id": "aaaaaaaa-0000-0000-0000-000000000002",
            "name": "Jira CreateIssue Agent",
            "metadata": {"isConversational": False, "storageVersion": "26.0.0"},
            "messages": [
                {"role": "System", "content": "You are an agentic assistant."},
            ],
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
            },
            "settings": {
                "model": "gpt-4o-2024-11-20",
                "maxTokens": 16384,
                "temperature": 0,
                "engine": "basic-v2",
            },
            "resources": [
                {
                    "$resourceType": "tool",
                    "type": "Integration",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "projectKey": {"type": "string", "title": "Project Key"},
                            "summary": {"type": "string", "title": "Summary"},
                            "description": {"type": "string", "title": "Description"},
                        },
                        "required": ["projectKey", "summary"],
                    },
                    "outputSchema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "key": {"type": "string"},
                        },
                    },
                    "arguments": {},
                    "settings": {"timeout": 0, "maxAttempts": 0, "retryDelay": 0},
                    "properties": {
                        "toolPath": "/CreateIssue",
                        "objectName": "CreateIssue",
                        "toolDisplayName": "Create Issue",
                        "toolDescription": "Creates a new Jira issue",
                        "method": "POST",
                        "bodyStructure": {
                            "contentType": "json",
                            "jsonBodySection": "body",
                        },
                        "connection": {
                            "id": "cccccccc-0000-0000-0000-000000000002",
                            "name": "Jira Connection",
                            "elementInstanceId": 0,
                            "apiBaseUri": "",
                            "state": "enabled",
                            "isDefault": False,
                            "connector": {
                                "key": "uipath-atlassian-jira",
                                "name": "Jira",
                                "enabled": True,
                            },
                            "folder": {"key": "bbbbbbbb-0000-0000-0000-000000000002"},
                            "solutionProperties": {
                                "resourceKey": "cccccccc-0000-0000-0000-000000000002"
                            },
                        },
                        "parameters": [
                            {
                                "name": "projectKey",
                                "displayName": "Project Key",
                                "type": "string",
                                "fieldLocation": "body",
                                "value": "{{prompt}}",
                                "fieldVariant": "dynamic",
                                "sortOrder": 1,
                                "required": True,
                            },
                            {
                                "name": "summary",
                                "displayName": "Summary",
                                "type": "string",
                                "fieldLocation": "body",
                                "value": "{{prompt}}",
                                "fieldVariant": "dynamic",
                                "sortOrder": 2,
                                "required": True,
                            },
                            {
                                "name": "issueType",
                                "displayName": "Issue Type",
                                "type": "string",
                                "fieldLocation": "body",
                                "value": "Task",
                                "fieldVariant": "static",
                                "sortOrder": 3,
                                "required": True,
                            },
                        ],
                    },
                    "name": "Create Issue",
                    "description": "Creates a new Jira issue",
                    "isEnabled": True,
                }
            ],
            "features": [],
        }

        # Test deserialization
        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        # Validate agent
        assert config.name == "Jira CreateIssue Agent"
        assert len(config.resources) == 1

        # Validate integration tool
        tool = config.resources[0]
        assert isinstance(tool, AgentIntegrationToolResourceConfig)
        assert tool.type == AgentToolType.INTEGRATION
        assert tool.name == "Create Issue"

        # Validate tool properties
        assert tool.properties.tool_path == "/CreateIssue"
        assert tool.properties.method == "POST"
        assert tool.properties.connection is not None
        assert tool.properties.connection.connector is not None
        assert tool.properties.connection.connector["key"] == "uipath-atlassian-jira"

        # Validate body structure
        assert tool.properties.body_structure is not None
        assert tool.properties.body_structure["contentType"] == "json"

        # Validate parameters
        assert len(tool.properties.parameters) == 3
        # Check for static parameter
        static_param = next(
            p for p in tool.properties.parameters if p.field_variant == "static"
        )
        assert static_param.name == "issueType"
        assert static_param.value == "Task"

        # Validate input_schema properties
        assert tool.input_schema is not None
        assert tool.input_schema["type"] == "object"
        assert "properties" in tool.input_schema
        assert "required" in tool.input_schema
        assert tool.input_schema["required"] == ["projectKey", "summary"]

        # Validate input_schema property fields
        schema_props = tool.input_schema["properties"]
        assert "projectKey" in schema_props
        assert schema_props["projectKey"]["type"] == "string"
        assert schema_props["projectKey"]["title"] == "Project Key"

        assert "summary" in schema_props
        assert schema_props["summary"]["type"] == "string"
        assert schema_props["summary"]["title"] == "Summary"

        assert "description" in schema_props
        assert schema_props["description"]["type"] == "string"
        assert schema_props["description"]["title"] == "Description"

    def test_agent_with_jira_search_issues_integration(self):
        """Test agent with Jira Search Issues integration tool"""

        json_data = {
            "version": "1.0.0",
            "id": "aaaaaaaa-0000-0000-0000-000000000003",
            "name": "Jira SearchIssues Agent",
            "metadata": {"isConversational": False, "storageVersion": "26.0.0"},
            "messages": [
                {"role": "System", "content": "You are an agentic assistant."},
            ],
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {
                "type": "object",
                "properties": {"content": {"type": "string"}},
            },
            "settings": {
                "model": "gpt-4o-2024-11-20",
                "maxTokens": 16384,
                "temperature": 0,
                "engine": "basic-v2",
            },
            "resources": [
                {
                    "$resourceType": "tool",
                    "type": "Integration",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "jql": {
                                "type": "string",
                                "title": "JQL Query",
                                "description": "Jira Query Language query string",
                            }
                        },
                        "required": ["jql"],
                    },
                    "outputSchema": {
                        "type": "object",
                        "properties": {
                            "issues": {"type": "array"},
                            "total": {"type": "integer"},
                        },
                    },
                    "arguments": {},
                    "settings": {"timeout": 0, "maxAttempts": 0, "retryDelay": 0},
                    "properties": {
                        "toolPath": "/SearchIssues",
                        "objectName": "SearchIssues",
                        "toolDisplayName": "Search Issues",
                        "toolDescription": "Search issues in Jira",
                        "method": "GET",
                        "bodyStructure": {
                            "contentType": "json",
                            "jsonBodySection": "body",
                        },
                        "connection": {
                            "id": "cccccccc-0000-0000-0000-000000000003",
                            "name": "Jira Connection",
                            "elementInstanceId": 0,
                            "apiBaseUri": "",
                            "state": "enabled",
                            "isDefault": False,
                            "connector": {
                                "key": "uipath-atlassian-jira",
                                "name": "Jira",
                                "enabled": True,
                            },
                            "folder": {"key": "bbbbbbbb-0000-0000-0000-000000000003"},
                            "solutionProperties": {
                                "resourceKey": "cccccccc-0000-0000-0000-000000000003"
                            },
                        },
                        "parameters": [
                            {
                                "name": "jql",
                                "displayName": "JQL Query",
                                "type": "string",
                                "fieldLocation": "query",
                                "value": "{{prompt}}",
                                "fieldVariant": "dynamic",
                                "sortOrder": 1,
                                "required": True,
                            }
                        ],
                    },
                    "name": "Search Issues",
                    "description": "Search issues in Jira",
                    "isEnabled": True,
                }
            ],
            "features": [],
        }

        # Test deserialization
        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        # Validate agent
        assert config.name == "Jira SearchIssues Agent"
        assert len(config.resources) == 1

        # Validate integration tool
        tool = config.resources[0]
        assert isinstance(tool, AgentIntegrationToolResourceConfig)
        assert tool.type == AgentToolType.INTEGRATION
        assert tool.name == "Search Issues"

        # Validate tool properties
        assert tool.properties.tool_path == "/SearchIssues"
        assert tool.properties.method == "GET"
        assert tool.properties.connection is not None
        assert tool.properties.connection.connector is not None
        assert tool.properties.connection.connector["key"] == "uipath-atlassian-jira"

        # Validate parameters - query parameter
        assert len(tool.properties.parameters) == 1
        param = tool.properties.parameters[0]
        assert param.name == "jql"
        assert param.field_location == "query"  # GET method uses query parameters
        assert param.required is True

        # Validate input_schema properties
        assert tool.input_schema is not None
        assert tool.input_schema["type"] == "object"
        assert "properties" in tool.input_schema
        assert "required" in tool.input_schema
        assert tool.input_schema["required"] == ["jql"]

        # Validate input_schema property fields
        schema_props = tool.input_schema["properties"]
        assert "jql" in schema_props
        assert schema_props["jql"]["type"] == "string"
        assert schema_props["jql"]["title"] == "JQL Query"
        assert schema_props["jql"]["description"] == "Jira Query Language query string"

    def test_agent_with_unknown_guardrail_type(self):
        """Test that AgentDefinition handles unknown guardrail types gracefully"""

        json_data = {
            "id": "test-unknown-guardrail",
            "name": "Agent with Unknown Guardrail",
            "version": "1.0.0",
            "settings": {
                "model": "gpt-4o-2024-11-20",
                "maxTokens": 16384,
                "temperature": 0,
                "engine": "basic-v1",
            },
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {"type": "object", "properties": {}},
            "resources": [],
            "guardrails": [
                {
                    "$guardrailType": "futureGuardrailType",
                    "id": "future-guardrail-id",
                    "name": "Future Guardrail",
                    "description": "A guardrail type that doesn't exist yet",
                    "someNewField": "someValue",
                    "action": {"$actionType": "block", "reason": "Test reason"},
                }
            ],
            "messages": [{"role": "system", "content": "Test system message"}],
        }

        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        assert config.guardrails is not None
        assert len(config.guardrails) == 1

        unknown_guardrail = config.guardrails[0]
        assert isinstance(unknown_guardrail, AgentUnknownGuardrail)
        assert unknown_guardrail.guardrail_type == "unknown"
        assert unknown_guardrail.raw["$guardrailType"] == "futureGuardrailType"
        assert unknown_guardrail.raw["name"] == "Future Guardrail"
        assert unknown_guardrail.raw["someNewField"] == "someValue"

    def test_agent_with_unknown_action_type(self):
        """Test that AgentDefinition handles unknown action types gracefully"""

        json_data = {
            "id": "test-unknown-action",
            "name": "Agent with Unknown Action",
            "version": "1.0.0",
            "settings": {
                "model": "gpt-4o-2024-11-20",
                "maxTokens": 16384,
                "temperature": 0,
                "engine": "basic-v1",
            },
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {"type": "object", "properties": {}},
            "resources": [],
            "guardrails": [
                {
                    "$guardrailType": "custom",
                    "id": "custom-guardrail-with-unknown-action",
                    "name": "Custom Guardrail",
                    "description": "Custom guardrail with unknown action",
                    "rules": [{"$ruleType": "always", "applyTo": "inputAndOutput"}],
                    "action": {
                        "$actionType": "futureActionType",
                        "someParameter": "someValue",
                        "anotherParameter": 123,
                    },
                    "enabledForEvals": True,
                    "selector": {"scopes": ["Agent"]},
                }
            ],
            "messages": [{"role": "system", "content": "Test system message"}],
        }

        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        assert config.guardrails is not None
        assert len(config.guardrails) == 1

        custom_guardrail = config.guardrails[0]
        assert isinstance(custom_guardrail, AgentCustomGuardrail)
        assert custom_guardrail.guardrail_type == "custom"

        action = custom_guardrail.action
        assert isinstance(action, AgentGuardrailUnknownAction)
        assert action.action_type == AgentGuardrailActionType.UNKNOWN
        assert action.details is not None
        assert action.details["$actionType"] == "futureActionType"
        assert action.details["someParameter"] == "someValue"
        assert action.details["anotherParameter"] == 123

    def test_agent_with_unknown_context_retrieval_mode(self):
        """Test that AgentDefinition handles unknown context retrieval modes gracefully"""

        json_data = {
            "id": "test-unknown-retrieval-mode",
            "name": "Agent with Unknown Retrieval Mode",
            "version": "1.0.0",
            "settings": {
                "model": "gpt-4o-2024-11-20",
                "maxTokens": 16384,
                "temperature": 0,
                "engine": "basic-v1",
            },
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {"type": "object", "properties": {}},
            "resources": [
                {
                    "$resourceType": "context",
                    "folderPath": "TestFolder",
                    "indexName": "Test Index",
                    "settings": {
                        "threshold": 0.5,
                        "resultCount": 5,
                        "retrievalMode": "FutureRetrievalMode",
                        "query": {"description": "Test query", "variant": "Dynamic"},
                    },
                    "name": "Test Context",
                    "description": "Context with unknown retrieval mode",
                }
            ],
            "messages": [{"role": "system", "content": "Test system message"}],
        }

        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        assert len(config.resources) == 1

        context_resource = config.resources[0]
        assert isinstance(context_resource, AgentContextResourceConfig)
        assert context_resource.resource_type == AgentResourceType.CONTEXT
        assert (
            context_resource.settings.retrieval_mode
            == AgentContextRetrievalMode.UNKNOWN
        )

    def test_agent_with_unknown_resource_type(self):
        """Test that AgentDefinition handles unknown resource types gracefully"""

        json_data = {
            "id": "test-unknown-resource",
            "name": "Agent with Unknown Resource",
            "version": "1.0.0",
            "settings": {
                "model": "gpt-4o-2024-11-20",
                "maxTokens": 16384,
                "temperature": 0,
                "engine": "basic-v1",
            },
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {"type": "object", "properties": {}},
            "resources": [
                {
                    "$resourceType": "futureResourceType",
                    "name": "Future Resource",
                    "description": "A resource type that doesn't exist yet",
                    "someNewField": "someValue",
                    "anotherField": {"nested": "data"},
                }
            ],
            "messages": [{"role": "system", "content": "Test system message"}],
        }

        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        assert len(config.resources) == 1

        unknown_resource = config.resources[0]
        assert isinstance(unknown_resource, AgentUnknownResourceConfig)
        assert unknown_resource.resource_type == AgentResourceType.UNKNOWN
        assert unknown_resource.name == "Future Resource"
        assert unknown_resource.description == "A resource type that doesn't exist yet"

    def test_agent_with_unknown_tool_type(self):
        """Test that AgentDefinition handles unknown tool types gracefully"""

        json_data = {
            "id": "test-unknown-tool",
            "name": "Agent with Unknown Tool",
            "version": "1.0.0",
            "settings": {
                "model": "gpt-4o-2024-11-20",
                "maxTokens": 16384,
                "temperature": 0,
                "engine": "basic-v1",
            },
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {"type": "object", "properties": {}},
            "resources": [
                {
                    "$resourceType": "tool",
                    "type": "FutureToolType",
                    "name": "Future Tool",
                    "description": "A tool type that doesn't exist yet",
                    "inputSchema": {"type": "object", "properties": {}},
                    "arguments": {},
                    "someNewToolField": "someValue",
                }
            ],
            "messages": [{"role": "system", "content": "Test system message"}],
        }

        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        assert len(config.resources) == 1

        tool_resource = config.resources[0]
        assert isinstance(tool_resource, AgentUnknownToolResourceConfig)
        assert tool_resource.resource_type == AgentResourceType.TOOL
        assert tool_resource.type == AgentToolType.UNKNOWN
        assert tool_resource.name == "Future Tool"
        assert tool_resource.description == "A tool type that doesn't exist yet"

    def test_agent_with_mixed_known_and_unknown_types(self):
        """Test that AgentDefinition handles a mix of known and unknown types"""

        json_data = {
            "id": "test-mixed-types",
            "name": "Agent with Mixed Types",
            "version": "1.0.0",
            "settings": {
                "model": "gpt-4o-2024-11-20",
                "maxTokens": 16384,
                "temperature": 0,
                "engine": "basic-v1",
            },
            "inputSchema": {"type": "object", "properties": {}},
            "outputSchema": {"type": "object", "properties": {}},
            "resources": [
                {
                    "$resourceType": "tool",
                    "type": "Agent",
                    "name": "Valid Agent Tool",
                    "description": "A valid agent tool",
                    "inputSchema": {"type": "object", "properties": {}},
                    "outputSchema": {"type": "object", "properties": {}},
                    "arguments": {},
                    "settings": {},
                    "properties": {
                        "processName": "TestAgent",
                        "folderPath": "TestFolder",
                    },
                },
                {
                    "$resourceType": "tool",
                    "type": "UnknownToolType",
                    "name": "Unknown Tool",
                    "description": "An unknown tool type",
                    "inputSchema": {"type": "object", "properties": {}},
                    "arguments": {},
                },
                {
                    "$resourceType": "context",
                    "folderPath": "TestFolder",
                    "indexName": "Test Index",
                    "settings": {
                        "threshold": 0,
                        "resultCount": 3,
                        "retrievalMode": "Semantic",
                    },
                    "name": "Valid Context",
                    "description": "A valid context resource",
                },
                {
                    "$resourceType": "unknownResourceType",
                    "name": "Unknown Resource",
                    "description": "An unknown resource type",
                },
            ],
            "guardrails": [
                {
                    "$guardrailType": "custom",
                    "id": "valid-custom",
                    "name": "Valid Custom Guardrail",
                    "description": "A valid custom guardrail",
                    "rules": [{"$ruleType": "always", "applyTo": "inputAndOutput"}],
                    "action": {"$actionType": "block", "reason": "Test reason"},
                    "enabledForEvals": True,
                    "selector": {"scopes": ["Agent"]},
                },
                {
                    "$guardrailType": "unknownGuardrailType",
                    "id": "unknown-guardrail",
                    "name": "Unknown Guardrail",
                    "description": "An unknown guardrail type",
                },
                {
                    "$guardrailType": "builtInValidator",
                    "id": "valid-builtin",
                    "name": "Valid Built-in Guardrail",
                    "description": "A valid built-in guardrail",
                    "validatorType": "pii_detection",
                    "validatorParameters": [],
                    "action": {
                        "$actionType": "unknownActionType",
                        "someParameter": "value",
                    },
                    "enabledForEvals": True,
                    "selector": {"scopes": ["Agent"]},
                },
            ],
            "messages": [{"role": "system", "content": "Test system message"}],
        }

        config: AgentDefinition = TypeAdapter(AgentDefinition).validate_python(
            json_data
        )

        # Validate resources
        assert len(config.resources) == 4

        # First resource should be a valid agent tool
        assert isinstance(config.resources[0], AgentProcessToolResourceConfig)
        assert config.resources[0].type == AgentToolType.AGENT

        # Second resource should be unknown tool
        assert isinstance(config.resources[1], AgentUnknownToolResourceConfig)
        assert config.resources[1].type == AgentToolType.UNKNOWN

        # Third resource should be valid context
        assert isinstance(config.resources[2], AgentContextResourceConfig)
        assert config.resources[2].resource_type == AgentResourceType.CONTEXT

        # Fourth resource should be unknown resource
        assert isinstance(config.resources[3], AgentUnknownResourceConfig)
        assert config.resources[3].resource_type == AgentResourceType.UNKNOWN

        # Validate guardrails
        assert config.guardrails is not None
        assert len(config.guardrails) == 3

        # First guardrail should be valid custom
        assert isinstance(config.guardrails[0], AgentCustomGuardrail)
        assert config.guardrails[0].guardrail_type == "custom"
        assert isinstance(config.guardrails[0].action, AgentGuardrailBlockAction)

        # Second guardrail should be unknown
        assert isinstance(config.guardrails[1], AgentUnknownGuardrail)
        assert config.guardrails[1].guardrail_type == "unknown"

        # Third guardrail should be valid built-in with unknown action
        assert isinstance(config.guardrails[2], AgentBuiltInValidatorGuardrail)
        assert config.guardrails[2].guardrail_type == "builtInValidator"
        assert isinstance(config.guardrails[2].action, AgentGuardrailUnknownAction)
        assert (
            config.guardrails[2].action.action_type == AgentGuardrailActionType.UNKNOWN
        )
