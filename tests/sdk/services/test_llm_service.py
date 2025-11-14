import json
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.llm_gateway_service import (
    ChatModels,
    EmbeddingModels,
    UiPathOpenAIService,
)
from uipath.models.llm_gateway import TextEmbedding


class TestOpenAIService:
    @pytest.fixture
    def config(self):
        return Config(base_url="https://example.com", secret="test_secret")

    @pytest.fixture
    def execution_context(self):
        return ExecutionContext()

    @pytest.fixture
    def openai_service(self, config, execution_context):
        return UiPathOpenAIService(config=config, execution_context=execution_context)

    @pytest.fixture
    def llm_service(self, config, execution_context):
        return UiPathOpenAIService(config=config, execution_context=execution_context)

    def test_init(self, config, execution_context):
        service = UiPathOpenAIService(
            config=config, execution_context=execution_context
        )
        assert service._config == config
        assert service._execution_context == execution_context

    @patch.object(UiPathOpenAIService, "request_async")
    @pytest.mark.asyncio
    async def test_embeddings(self, mock_request, openai_service):
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0, "object": "embedding"}],
            "model": "text-embedding-ada-002",
            "object": "list",
            "usage": {"prompt_tokens": 4, "total_tokens": 4},
        }
        mock_request.return_value = mock_response

        # Call the method
        result = await openai_service.embeddings(input="Test input")

        # Assertions
        mock_request.assert_called_once()
        assert isinstance(result, TextEmbedding)
        assert result.data[0].embedding == [0.1, 0.2, 0.3]
        assert result.model == "text-embedding-ada-002"
        assert result.usage.prompt_tokens == 4

    @patch.object(UiPathOpenAIService, "request_async")
    @pytest.mark.asyncio
    async def test_embeddings_with_custom_model(self, mock_request, openai_service):
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0, "object": "embedding"}],
            "model": "text-embedding-3-large",
            "object": "list",
            "usage": {"prompt_tokens": 4, "total_tokens": 4},
        }
        mock_request.return_value = mock_response

        # Call the method with custom model
        result = await openai_service.embeddings(
            input="Test input", embedding_model=EmbeddingModels.text_embedding_3_large
        )

        # Assertions for the result
        mock_request.assert_called_once()
        assert result.model == "text-embedding-3-large"
        assert len(result.data) == 1
        assert result.data[0].embedding == [0.1, 0.2, 0.3]
        assert result.data[0].index == 0
        assert result.object == "list"
        assert result.usage.prompt_tokens == 4
        assert result.usage.total_tokens == 4

    @patch.object(UiPathOpenAIService, "request_async")
    @pytest.mark.asyncio
    async def test_complex_company_pydantic_model(self, mock_request, llm_service):
        """Test using complex Company Pydantic model as response_format."""

        # Define the complex nested models
        class Task(BaseModel):
            task_id: int
            description: str
            completed: bool

        class Project(BaseModel):
            project_id: int
            name: str
            tasks: List[Task]

        class Team(BaseModel):
            team_id: int
            team_name: str
            members: List[str]
            projects: List[Project]

        class Department(BaseModel):
            department_id: int
            department_name: str
            teams: List[Team]

        class Company(BaseModel):
            company_id: int
            company_name: str
            departments: List[Department]

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "chatcmpl-test123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4o-mini-2024-07-18",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {
                                "company_id": 1,
                                "company_name": "FutureTech Ltd",
                                "departments": [
                                    {
                                        "department_id": 1,
                                        "department_name": "Engineering",
                                        "teams": [
                                            {
                                                "team_id": 1,
                                                "team_name": "Backend Team",
                                                "members": [
                                                    "john@futuretech.com",
                                                    "jane@futuretech.com",
                                                ],
                                                "projects": [
                                                    {
                                                        "project_id": 1,
                                                        "name": "API Development",
                                                        "tasks": [
                                                            {
                                                                "task_id": 1,
                                                                "description": "Design REST endpoints",
                                                                "completed": True,
                                                            },
                                                            {
                                                                "task_id": 2,
                                                                "description": "Implement authentication",
                                                                "completed": False,
                                                            },
                                                        ],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                    {
                                        "department_id": 2,
                                        "department_name": "Marketing",
                                        "teams": [
                                            {
                                                "team_id": 2,
                                                "team_name": "Digital Marketing",
                                                "members": ["sarah@futuretech.com"],
                                                "projects": [
                                                    {
                                                        "project_id": 2,
                                                        "name": "Social Media Campaign",
                                                        "tasks": [
                                                            {
                                                                "task_id": 3,
                                                                "description": "Create content calendar",
                                                                "completed": True,
                                                            }
                                                        ],
                                                    }
                                                ],
                                            }
                                        ],
                                    },
                                ],
                            }
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 150,
                "completion_tokens": 300,
                "total_tokens": 450,
            },
        }
        mock_request.return_value = mock_response

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Respond with structured JSON according to this schema:\n"
                    "Company -> departments -> teams -> projects -> tasks.\n"
                    "Each company has a company_id and company_name.\n"
                    "Each department has a department_id and department_name.\n"
                    "Each team has a team_id, team_name, members (email addresses), and projects.\n"
                    "Each project has a project_id, name, and tasks.\n"
                    "Each task has a task_id, description, and completed status."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Give me an example of a software company called 'FutureTech Ltd' with two departments: "
                    "Engineering and Marketing. Each department should have at least one team, with projects and tasks."
                ),
            },
        ]

        result = await llm_service.chat_completions(
            messages=messages,
            model=ChatModels.gpt_4o_mini_2024_07_18,
            response_format=Company,  # Pass BaseModel directly instead of dict
            max_tokens=2000,
            temperature=0,
        )

        # Validate the response
        assert result is not None
        assert len(result.choices) > 0
        assert result.choices[0].message.content is not None

        # Parse and validate the JSON response
        response_json = json.loads(result.choices[0].message.content)

        # Validate the structure matches our Company model
        assert "company_id" in response_json
        assert "company_name" in response_json
        assert "departments" in response_json
        assert response_json["company_name"] == "FutureTech Ltd"
        assert len(response_json["departments"]) >= 2

        # Check for Engineering and Marketing departments
        dept_names = [dept["department_name"] for dept in response_json["departments"]]
        assert "Engineering" in dept_names
        assert "Marketing" in dept_names

        # Validate that each department has teams with proper structure
        for department in response_json["departments"]:
            assert "teams" in department
            assert len(department["teams"]) >= 1

            # Validate team structure
            for team in department["teams"]:
                assert "team_id" in team
                assert "team_name" in team
                assert "members" in team
                assert "projects" in team

                # Validate projects and tasks
                for project in team["projects"]:
                    assert "project_id" in project
                    assert "name" in project
                    assert "tasks" in project

                    for task in project["tasks"]:
                        assert "task_id" in task
                        assert "description" in task
                        assert "completed" in task

        # Try to parse it with our Pydantic model to ensure it's completely valid
        company_instance = Company.model_validate(response_json)
        assert company_instance.company_name == "FutureTech Ltd"
        assert len(company_instance.departments) >= 2

    @patch.object(UiPathOpenAIService, "request_async")
    @pytest.mark.asyncio
    async def test_optional_request_format_model(self, mock_request, llm_service):
        """Test using complex Company Pydantic model as response_format."""

        class Article(BaseModel):
            title: Optional[str] = None

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "chatcmpl-test123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4o-mini-2024-07-18",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "{}",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 150,
                "completion_tokens": 300,
                "total_tokens": 450,
            },
        }
        mock_request.return_value = mock_response

        messages = [
            {
                "role": "system",
                "content": "system-content",
            },
            {
                "role": "user",
                "content": "user-content",
            },
        ]

        result = await llm_service.chat_completions(
            messages=messages,
            model=ChatModels.gpt_4o_mini_2024_07_18,
            response_format=Article,  # Pass BaseModel directly instead of dict
            max_tokens=2000,
            temperature=0,
        )
        captured_request = mock_request.call_args[1]["json"]
        expected_request = {
            "messages": [
                {"role": "system", "content": "system-content"},
                {"role": "user", "content": "user-content"},
            ],
            "max_tokens": 2000,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "article",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "title": {
                                "anyOf": [{"type": "string"}, {"type": "null"}],
                                "default": None,
                            }
                        },
                        "required": ["title"],
                    },
                },
            },
        }

        # validate the request to LLM gateway
        assert expected_request == captured_request

        # Validate the response
        assert result is not None
        assert len(result.choices) > 0
        assert result.choices[0].message.content is not None

        # Parse and validate the JSON response
        response_json = json.loads(result.choices[0].message.content)

        # Validate the structure matches our Company model
        assert response_json == {}

        # Try to parse it with our Pydantic model to ensure it's completely valid
        article_instance = Article.model_validate(response_json)
        assert article_instance.title is None
