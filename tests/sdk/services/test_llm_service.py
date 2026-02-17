import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.chat import (
    ChatModels,
    EmbeddingModels,
    TextEmbedding,
    UiPathOpenAIService,
)


class TestOpenAIService:
    @pytest.fixture
    def config(self):
        return UiPathApiConfig(base_url="https://example.com", secret="test_secret")

    @pytest.fixture
    def execution_context(self):
        return UiPathExecutionContext()

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
            tasks: list[Task]

        class Team(BaseModel):
            team_id: int
            team_name: str
            members: list[str]
            projects: list[Project]

        class Department(BaseModel):
            department_id: int
            department_name: str
            teams: list[Team]

        class Company(BaseModel):
            company_id: int
            company_name: str
            departments: list[Department]

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
            model=ChatModels.gpt_4_1_mini_2025_04_14,
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
            title: str | None = None

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
            model=ChatModels.gpt_4_1_mini_2025_04_14,
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


class TestNormalizedLlmServiceClaudeFiltering:
    """Test that Claude models correctly filter out OpenAI-specific parameters.

    The UiPath Normalized API gateway passes parameters through to the underlying
    provider. Claude/Anthropic models do NOT support n, frequency_penalty,
    presence_penalty, or top_p, and sending them causes 400 errors.
    """

    @pytest.fixture
    def config(self):
        return UiPathApiConfig(base_url="https://example.com", secret="test_secret")

    @pytest.fixture
    def execution_context(self):
        return UiPathExecutionContext()

    @pytest.fixture
    def llm_service(self, config, execution_context):
        from uipath.platform.chat._llm_gateway_service import UiPathLlmChatService

        return UiPathLlmChatService(config=config, execution_context=execution_context)

    @patch(
        "uipath.platform.chat._llm_gateway_service.UiPathLlmChatService.request_async"
    )
    @pytest.mark.asyncio
    async def test_claude_model_excludes_openai_params(self, mock_request, llm_service):
        """Test that Claude models do not include n, frequency_penalty, presence_penalty, top_p."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "anthropic.claude-haiku-4-5-20251001-v1:0",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_request.return_value = mock_response

        await llm_service.chat_completions(
            messages=[{"role": "user", "content": "Hello"}],
            model="anthropic.claude-haiku-4-5-20251001-v1:0",
            max_tokens=1000,
            temperature=0,
        )

        # Get the request body and headers
        call_kwargs = mock_request.call_args[1]
        request_body = call_kwargs["json"]
        headers = call_kwargs["headers"]

        # Claude models should NOT have these OpenAI-specific params
        assert "n" not in request_body, "Claude request must not include 'n'"
        assert "frequency_penalty" not in request_body, (
            "Claude request must not include 'frequency_penalty'"
        )
        assert "presence_penalty" not in request_body, (
            "Claude request must not include 'presence_penalty'"
        )
        assert "top_p" not in request_body, "Claude request must not include 'top_p'"

        # Model is sent in headers, not body (Normalized API pattern)
        assert (
            headers["X-UiPath-LlmGateway-NormalizedApi-ModelName"]
            == "anthropic.claude-haiku-4-5-20251001-v1:0"
        )
        # Basic params should still be in the body
        assert request_body["max_tokens"] == 1000
        assert request_body["temperature"] == 0

    @patch(
        "uipath.platform.chat._llm_gateway_service.UiPathLlmChatService.request_async"
    )
    @pytest.mark.asyncio
    async def test_openai_model_includes_all_params(self, mock_request, llm_service):
        """Test that OpenAI models DO include n, frequency_penalty, presence_penalty."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4o-mini-2024-07-18",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_request.return_value = mock_response

        await llm_service.chat_completions(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o-mini-2024-07-18",
            max_tokens=1000,
            temperature=0,
        )

        call_kwargs = mock_request.call_args[1]
        request_body = call_kwargs["json"]

        # OpenAI models should have all params
        assert "n" in request_body, "OpenAI request must include 'n'"
        assert "frequency_penalty" in request_body, (
            "OpenAI request must include 'frequency_penalty'"
        )
        assert "presence_penalty" in request_body, (
            "OpenAI request must include 'presence_penalty'"
        )

    @patch(
        "uipath.platform.chat._llm_gateway_service.UiPathLlmChatService.request_async"
    )
    @pytest.mark.asyncio
    async def test_claude_sonnet_45_excluded_params(self, mock_request, llm_service):
        """Test Claude Sonnet 4.5 specifically, since it was failing in production."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "anthropic.claude-sonnet-4-5-20250929-v1:0",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_request.return_value = mock_response

        await llm_service.chat_completions(
            messages=[{"role": "user", "content": "Hello"}],
            model="anthropic.claude-sonnet-4-5-20250929-v1:0",
            max_tokens=8000,
            temperature=0,
        )

        call_kwargs = mock_request.call_args[1]
        request_body = call_kwargs["json"]

        assert "n" not in request_body
        assert "frequency_penalty" not in request_body
        assert "presence_penalty" not in request_body
        assert "top_p" not in request_body
        assert request_body["max_tokens"] == 8000
