from pydantic import TypeAdapter

from uipath.agent.models.agent import AgentResourceType, AgentUnknownResourceConfig
from uipath.agent.models.evals import AgentEvalsDefinition


class TestEvalsAgentDefinition:
    def test_evals_agent_loads_complete_json(self):
        """Test that EvalsAgentDefinition can load from the complete JSON with evaluators and evaluation sets"""

        json_data = {
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
                                    "type": "UserId",
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
                        "processName": "Test-Basic-Agent",
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
            "evaluators": [
                {
                    "fileName": "evaluator-default.json",
                    "id": "c395579a-4e15-425e-b400-a630a63a6237",
                    "name": "Default Evaluator",
                    "description": "An evaluator that uses a LLM to score the similarity of the actual output to the expected output",
                    "category": 1,
                    "type": 5,
                    "prompt": "As an expert evaluator, analyze the semantic similarity of these JSON contents to determine a score from 0-100. Focus on comparing the meaning and contextual equivalence of corresponding fields, accounting for alternative valid expressions, synonyms, and reasonable variations in language while maintaining high standards for accuracy and completeness. Provide your score with a justification, explaining briefly and concisely why you gave that score.\n----\nExpectedOutput:\n{{ExpectedOutput}}\n----\nActualOutput:\n{{ActualOutput}}\n",
                    "model": "same-as-agent",
                    "targetOutputKey": "*",
                    "createdAt": "2025-06-09T18:20:06.080Z",
                    "updatedAt": "2025-06-09T18:20:06.080Z",
                },
                {
                    "fileName": "evaluator-default-simulation.json",
                    "id": "3c82e1a2-0112-4e3b-ba45-25f379298faa",
                    "name": "Default Simulation Evaluator",
                    "description": "An evaluator that uses a LLM to score the similarity of the actual output to the expected output",
                    "category": 3,
                    "type": 7,
                    "prompt": "As an expert evaluator, determine how well the agent did on a scale of 0-100. Focus on if the simulation was successful and if the agent behaved according to the expected output accounting for alternative valid expressions, and reasonable variations in language while maintaining high standards for accuracy and completeness. Provide your score with a justification, explaining briefly and concisely why you gave that score.\n----\nUserOrSyntheticInputGivenToAgent:\n{{UserOrSyntheticInput}}\n----\nSimulationInstructions:\n{{SimulationInstructions}}\n----\nExpectedAgentBehavior:\n{{ExpectedAgentBehavior}}\n----\nAgentRunHistory:\n{{AgentRunHistory}}\n",
                    "model": "same-as-agent",
                    "targetOutputKey": "*",
                    "createdAt": "2025-06-09T18:20:06.335Z",
                    "updatedAt": "2025-06-09T18:20:06.335Z",
                },
                {
                    "fileName": "evaluator-default-trajectory.json",
                    "id": "a544a330-5e6b-4dca-a4e5-ea5fd024779b",
                    "name": "Default Trajectory Evaluator",
                    "description": "An evaluator that judges the agent based on it's run history and expected behavior",
                    "category": 3,
                    "type": 7,
                    "prompt": "As an expert evaluator, determine how well the agent did on a scale of 0-100. Focus on if the simulation was successful and if the agent behaved according to the expected output accounting for alternative valid expressions, and reasonable variations in language while maintaining high standards for accuracy and completeness. Provide your score with a justification, explaining briefly and concisely why you gave that score.\n----\nUserOrSyntheticInputGivenToAgent:\n{{UserOrSyntheticInput}}\n----\nSimulationInstructions:\n{{SimulationInstructions}}\n----\nExpectedAgentBehavior:\n{{ExpectedAgentBehavior}}\n----\nAgentRunHistory:\n{{AgentRunHistory}}\n",
                    "model": "same-as-agent",
                    "targetOutputKey": "*",
                    "createdAt": "2025-06-26T17:45:39.651Z",
                    "updatedAt": "2025-06-26T17:45:39.651Z",
                },
            ],
            "evaluationSets": [
                {
                    "fileName": "evaluation-set-1757012098378.json",
                    "id": "d649e632-1582-4cb1-9e68-c3aff46c2802",
                    "name": "Loan Agent Evaluation Set",
                    "batchSize": 10,
                    "evaluatorRefs": [
                        "c395579a-4e15-425e-b400-a630a63a6237",
                        "a544a330-5e6b-4dca-a4e5-ea5fd024779b",
                    ],
                    "evaluations": [
                        {
                            "id": "7309b5dc-46c5-46cb-b6cb-dbb5d9ff5ccf",
                            "name": "Low Credit Score Rejection",
                            "inputs": {},
                            "evaluationCriterias": {
                                "Default Evaluator": {"content": '"rejected"'}
                            },
                            "simulationInstructions": "The A2ALoanCreditRatingTool should return a credit rating of 650.",
                            "expectedAgentBehavior": "The agent should reject the loan application due to the credit rating being below 700.",
                            "simulateInput": True,
                            "inputGenerationInstructions": "Generate a loan application query with name, loan amount, and loan type (mortgage or personal loan).",
                            "simulateTools": True,
                            "toolsToSimulate": [
                                {"name": "A2ALoanCreditRatingTool"},
                                {"name": "escalate_escalation_1"},
                            ],
                            "evalSetId": "7e4a91a3-e387-47c6-b4e2-75cd503a77d3",
                            "createdAt": "2025-09-04T18:54:58.378Z",
                            "updatedAt": "2025-09-04T18:55:55.416Z",
                        },
                        {
                            "id": "f8e31cc4-1e70-4043-80df-eac1439f6120",
                            "name": "High Credit Score Small Loan Approval",
                            "inputs": {},
                            "evaluationCriterias": {},
                            "simulationInstructions": "The A2ALoanCreditRatingTool should return a credit rating of 850.",
                            "expectedAgentBehavior": "The agent should approve the loan application due to the credit rating being above 800 and the loan amount being less than $10,000.",
                            "simulateInput": True,
                            "inputGenerationInstructions": "Generate a loan application query with name, loan amount under $10,000, and loan type (mortgage or personal loan).",
                            "simulateTools": True,
                            "toolsToSimulate": [
                                {"name": "A2ALoanCreditRatingTool"},
                                {"name": "escalate_escalation_1"},
                            ],
                            "evalSetId": "7e4a91a3-e387-47c6-b4e2-75cd503a77d3",
                            "createdAt": "2025-09-04T18:54:58.378Z",
                            "updatedAt": "2025-09-04T18:54:58.378Z",
                        },
                        {
                            "id": "73a5dc37-9147-4184-9427-dd7306ed8e71",
                            "name": "Manual Review Escalation",
                            "inputs": {},
                            "evaluationCriterias": {},
                            "simulationInstructions": "The A2ALoanCreditRatingTool should return a credit rating of 750.",
                            "expectedAgentBehavior": "The agent should escalate the application for manual review as the credit rating is between 700 and 800.",
                            "simulateInput": True,
                            "inputGenerationInstructions": "Generate a loan application query with name, loan amount over $10,000, and loan type (mortgage or personal loan).",
                            "simulateTools": True,
                            "toolsToSimulate": [
                                {"name": "A2ALoanCreditRatingTool"},
                                {"name": "escalate_escalation_1"},
                            ],
                            "evalSetId": "7e4a91a3-e387-47c6-b4e2-75cd503a77d3",
                            "createdAt": "2025-09-04T18:54:58.378Z",
                            "updatedAt": "2025-09-04T18:54:58.378Z",
                        },
                        {
                            "id": "5c8f2030-0129-478f-8c56-140c287f22ab",
                            "name": "Incomplete Application",
                            "inputs": {},
                            "evaluationCriterias": {},
                            "simulationInstructions": "No tool calls should be made.",
                            "expectedAgentBehavior": "The agent should inform the user that all mandatory details (name, loan amount, and loan type) are required to process the application.",
                            "simulateInput": True,
                            "inputGenerationInstructions": "Generate a loan application query missing one of the mandatory details (name, loan amount, or loan type).",
                            "simulateTools": True,
                            "toolsToSimulate": [
                                {"name": "A2ALoanCreditRatingTool"},
                                {"name": "escalate_escalation_1"},
                            ],
                            "evalSetId": "7e4a91a3-e387-47c6-b4e2-75cd503a77d3",
                            "createdAt": "2025-09-04T18:54:58.378Z",
                            "updatedAt": "2025-09-04T18:54:58.378Z",
                        },
                    ],
                    "modelSettings": [],
                    "createdAt": "2025-09-04T18:54:58.379Z",
                    "updatedAt": "2025-09-04T18:55:55.416Z",
                },
                {
                    "fileName": "evaluation-set-default.json",
                    "id": "aee3efd3-252a-439b-baf7-565cef3d0ef4",
                    "name": "Default Evaluation Set",
                    "batchSize": 10,
                    "evaluatorRefs": ["c395579a-4e15-425e-b400-a630a63a6237"],
                    "evaluations": [],
                    "modelSettings": [],
                    "createdAt": "2025-06-09T18:20:06.644Z",
                    "updatedAt": "2025-06-09T18:20:06.644Z",
                },
                {
                    "fileName": "evaluation-set-simulation-default-simulation_set.json",
                    "id": "f52b67e1-6fe5-4cb6-966a-082f2ccbf0ae",
                    "name": "Default Simulation Evaluation Set",
                    "batchSize": 10,
                    "evaluatorRefs": ["3c82e1a2-0112-4e3b-ba45-25f379298faa"],
                    "evaluations": [],
                    "modelSettings": [],
                    "createdAt": "2025-06-09T18:20:07.045Z",
                    "updatedAt": "2025-06-09T18:20:07.045Z",
                },
            ],
            "version": "1.0.0",
        }

        # Test that the model loads without errors
        config: AgentEvalsDefinition = TypeAdapter(
            AgentEvalsDefinition
        ).validate_python(json_data)

        # Basic assertions
        assert isinstance(config, AgentEvalsDefinition)
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

    def test_evals_agent_loads_unknown_resource_json(self):
        """Test that EvalsAgentDefinition can load JSON with an unknown resource type"""

        json_data = {
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

        config: AgentEvalsDefinition = TypeAdapter(
            AgentEvalsDefinition
        ).validate_python(json_data)

        # Basic assertions
        assert isinstance(config, AgentEvalsDefinition)
        assert config.id == "b2564199-e479-4b6f-9336-dc50f457afda"
        assert config.name == "Agent"
        assert config.version == "1.0.0"
        assert config.settings.engine == "basic-v1"
        assert config.settings.max_tokens == 16384

        # Validate resources
        assert len(config.resources) == 1
        resource = config.resources[0]

        # Should fall back to UnknownAgentResourceConfig
        assert isinstance(resource, AgentUnknownResourceConfig)
        assert resource.resource_type == "unknown"
        assert resource.name == "mystery_resource"
        assert resource.extraField == {"foo": "bar"}
        assert resource.slug == "mystery-resource"
