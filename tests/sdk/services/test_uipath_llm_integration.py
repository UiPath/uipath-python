import json
import os
from unittest.mock import MagicMock, patch

import pytest

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.llm_gateway_service import (
    ChatModels,
    UiPathLlmChatService,
)
from uipath.models.llm_gateway import (
    AutoToolChoice,
    SpecificToolChoice,
    ToolDefinition,
    ToolFunctionDefinition,
    ToolParametersDefinition,
    ToolPropertyDefinition,
)


def get_env_var(name: str) -> str:
    """Get environment variable or skip test if not present."""
    value = os.environ.get(name)
    if value is None:
        pytest.skip(f"Environment variable {name} is not set")
    return value


class TestUiPathLLMIntegration:
    @pytest.fixture
    def llm_service(self):
        """Create a UiPathLLMService instance with environment variables."""
        # In a real-world scenario, these would be environment variables
        base_url = get_env_var("UIPATH_URL")
        api_key = get_env_var("UIPATH_ACCESS_TOKEN")

        config = Config(base_url=base_url, secret=api_key)
        execution_context = ExecutionContext()
        return UiPathLlmChatService(config=config, execution_context=execution_context)

    @pytest.mark.asyncio
    async def test_basic_chat_completions(self, llm_service):
        """Test basic chat completions functionality."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"},
        ]

        result = await llm_service.chat_completions(
            messages=messages,
            model=ChatModels.gpt_4o_mini_2024_07_18,
            max_tokens=50,
            temperature=0,
        )

        # Validate the response
        assert result is not None
        assert hasattr(result, "id")
        assert hasattr(result, "choices")
        assert len(result.choices) > 0
        assert hasattr(result.choices[0], "message")
        assert hasattr(result.choices[0].message, "content")
        assert "Paris" in result.choices[0].message.content

    @pytest.mark.asyncio
    async def test_tool_call_required(self, llm_service):
        """Test the tool call functionality with a specific required tool."""
        messages = [
            {
                "role": "system",
                "content": "You are given two tools/functions and a user and password. You must first call test_tool with the given credentials then call submit_answer with the result. If the result is nested, extract the result string and pass it to submit_answer. Do not respond with text, only call the tools/functions.",
            },
            {"role": "user", "content": "username: John, password: 1234"},
        ]

        # Define the test_tool
        test_tool = ToolDefinition(
            type="function",
            function=ToolFunctionDefinition(
                name="test_tool",
                description="call this to obtain the result",
                parameters=ToolParametersDefinition(
                    type="object",
                    properties={
                        "name": ToolPropertyDefinition(
                            type="string", description="the name of the user"
                        ),
                        "password": ToolPropertyDefinition(
                            type="string", description="the password of the user"
                        ),
                    },
                    required=["name", "password"],
                ),
            ),
        )

        # Define tool choice to specifically use test_tool
        tool_choice = SpecificToolChoice(type="tool", name="test_tool")

        result = await llm_service.chat_completions(
            messages=messages,
            model=ChatModels.gpt_4o_mini_2024_07_18,
            max_tokens=250,
            temperature=0,
            tools=[test_tool],
            tool_choice=tool_choice,
        )

        # Validate the response
        assert result is not None
        assert len(result.choices) > 0
        assert result.choices[0].message.tool_calls is not None
        assert len(result.choices[0].message.tool_calls) > 0
        assert result.choices[0].message.tool_calls[0].name == "test_tool"
        assert "name" in result.choices[0].message.tool_calls[0].arguments
        assert result.choices[0].message.tool_calls[0].arguments["name"] == "John"
        assert "password" in result.choices[0].message.tool_calls[0].arguments
        assert result.choices[0].message.tool_calls[0].arguments["password"] == "1234"

    @pytest.mark.asyncio
    async def test_chat_with_conversation_history(self, llm_service):
        """Test chat completions with a conversation history including assistant messages."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hi my name is John"},
            {"content": "Hello John! How can I assist you today?", "role": "assistant"},
            {"role": "user", "content": "What is my name?"},
        ]

        # Define the test_tool but with auto tool choice
        test_tool = ToolDefinition(
            type="function",
            function=ToolFunctionDefinition(
                name="test_tool",
                description="call this to obtain the result",
                parameters=ToolParametersDefinition(
                    type="object",
                    properties={
                        "name": ToolPropertyDefinition(
                            type="string", description="the name of the user"
                        ),
                        "password": ToolPropertyDefinition(
                            type="string", description="the password of the user"
                        ),
                    },
                    required=["name", "password"],
                ),
            ),
        )

        # Use auto tool choice
        tool_choice = AutoToolChoice(type="auto")

        result = await llm_service.chat_completions(
            messages=messages,
            model=ChatModels.gpt_4o_mini_2024_07_18,
            max_tokens=250,
            temperature=0,
            frequency_penalty=1,
            presence_penalty=1,
            tools=[test_tool],
            tool_choice=tool_choice,
        )

        # Validate the response
        assert result is not None
        assert len(result.choices) > 0
        assert result.choices[0].message.content is not None
        assert "John" in result.choices[0].message.content
        # The model chose to respond with text instead of using the tool
        assert (
            result.choices[0].message.tool_calls is None
            or len(result.choices[0].message.tool_calls) == 0
        )

    @pytest.mark.asyncio
    async def test_no_tools(self, llm_service):
        """Test chat completions without any tools."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write a haiku about Python programming."},
        ]

        result = await llm_service.chat_completions(
            messages=messages,
            model=ChatModels.gpt_4o_mini_2024_07_18,
            max_tokens=100,
            temperature=0.7,
        )

        # Validate the response
        assert result is not None
        assert len(result.choices) > 0
        assert result.choices[0].message.content is not None
        assert len(result.choices[0].message.content.strip()) > 0
        # No tools were provided, so no tool calls should be in the response
        assert (
            result.choices[0].message.tool_calls is None
            or len(result.choices[0].message.tool_calls) == 0
        )


class TestUiPathLLMServiceMocked:
    @pytest.fixture
    def config(self):
        return Config(base_url="https://example.com", secret="test_secret")

    @pytest.fixture
    def execution_context(self):
        return ExecutionContext()

    @pytest.fixture
    def llm_service(self, config, execution_context):
        return UiPathLlmChatService(config=config, execution_context=execution_context)

    def test_init(self, config, execution_context):
        service = UiPathLlmChatService(
            config=config, execution_context=execution_context
        )
        assert service._config == config
        assert service._execution_context == execution_context

    @pytest.mark.asyncio
    @patch.object(UiPathLlmChatService, "request_async")
    async def test_basic_chat_completions_mocked(self, mock_request, llm_service):
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677858242,
            "model": "gpt-4o-mini-2024-07-18",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "The capital of France is Paris.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 30,
                "completion_tokens": 10,
                "total_tokens": 40,
                "cache_read_input_tokens": None,
            },
        }
        mock_request.return_value = mock_response

        # Test messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"},
        ]

        # Call the method
        result = await llm_service.chat_completions(
            messages=messages,
            model=ChatModels.gpt_4o_mini_2024_07_18,
            max_tokens=50,
            temperature=0,
        )

        # Assertions
        mock_request.assert_called_once()
        assert result.id == "chatcmpl-123"
        assert len(result.choices) == 1
        assert result.choices[0].message.content == "The capital of France is Paris."
        assert "Paris" in result.choices[0].message.content
        assert result.usage.prompt_tokens == 30
        assert result.usage.completion_tokens == 10

        # Verify the correct endpoint and payload
        args, kwargs = mock_request.call_args
        assert "/llmgateway_/api/chat/completions" in args[1]
        assert json.loads(kwargs["content"])["messages"] == messages
        assert json.loads(kwargs["content"])["max_tokens"] == 50
        assert json.loads(kwargs["content"])["temperature"] == 0

    @pytest.mark.asyncio
    @patch.object(UiPathLlmChatService, "request_async")
    async def test_tool_call_required_mocked(self, mock_request, llm_service):
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "chatcmpl-456",
            "object": "chat.completion",
            "created": 1677858242,
            "model": "gpt-4o-mini-2024-07-18",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_abc123",
                                "name": "test_tool",
                                "arguments": {"name": "John", "password": "1234"},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 25,
                "total_tokens": 75,
                "cache_read_input_tokens": None,
            },
        }
        mock_request.return_value = mock_response

        # Test messages
        messages = [
            {
                "role": "system",
                "content": "You are given two tools/functions and a user and password. You must first call test_tool with the given credentials then call submit_answer with the result. If the result is nested, extract the result string and pass it to submit_answer. Do not respond with text, only call the tools/functions.",
            },
            {"role": "user", "content": "username: John, password: 1234"},
        ]

        # Define the test_tool
        test_tool = ToolDefinition(
            type="function",
            function=ToolFunctionDefinition(
                name="test_tool",
                description="call this to obtain the result",
                parameters=ToolParametersDefinition(
                    type="object",
                    properties={
                        "name": ToolPropertyDefinition(
                            type="string", description="the name of the user"
                        ),
                        "password": ToolPropertyDefinition(
                            type="string", description="the password of the user"
                        ),
                    },
                    required=["name", "password"],
                ),
            ),
        )

        # Define tool choice
        tool_choice = SpecificToolChoice(type="tool", name="test_tool")

        # Call the method
        result = await llm_service.chat_completions(
            messages=messages,
            model=ChatModels.gpt_4o_mini_2024_07_18,
            max_tokens=250,
            temperature=0,
            tools=[test_tool],
            tool_choice=tool_choice,
        )

        # Assertions
        mock_request.assert_called_once()
        assert result.id == "chatcmpl-456"
        assert len(result.choices) == 1
        assert result.choices[0].message.tool_calls is not None
        assert len(result.choices[0].message.tool_calls) == 1
        assert result.choices[0].message.tool_calls[0].name == "test_tool"
        assert result.choices[0].message.tool_calls[0].arguments["name"] == "John"
        assert result.choices[0].message.tool_calls[0].arguments["password"] == "1234"

    @pytest.mark.asyncio
    @patch.object(UiPathLlmChatService, "request_async")
    async def test_chat_with_conversation_history_mocked(
        self, mock_request, llm_service
    ):
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "chatcmpl-789",
            "object": "chat.completion",
            "created": 1677858242,
            "model": "gpt-4o-mini-2024-07-18",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Your name is John, as you mentioned earlier.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 70,
                "completion_tokens": 15,
                "total_tokens": 85,
                "cache_read_input_tokens": None,
            },
        }
        mock_request.return_value = mock_response

        # Test messages with conversation history
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hi my name is John"},
            {"content": "Hello John! How can I assist you today?", "role": "assistant"},
            {"role": "user", "content": "What is my name?"},
        ]

        # Define test tool
        test_tool = ToolDefinition(
            type="function",
            function=ToolFunctionDefinition(
                name="test_tool",
                description="call this to obtain the result",
                parameters=ToolParametersDefinition(
                    type="object",
                    properties={
                        "name": ToolPropertyDefinition(
                            type="string", description="the name of the user"
                        ),
                        "password": ToolPropertyDefinition(
                            type="string", description="the password of the user"
                        ),
                    },
                    required=["name", "password"],
                ),
            ),
        )

        # Use auto tool choice
        tool_choice = AutoToolChoice(type="auto")

        # Call the method
        result = await llm_service.chat_completions(
            messages=messages,
            model=ChatModels.gpt_4o_mini_2024_07_18,
            max_tokens=250,
            temperature=0,
            frequency_penalty=1,
            presence_penalty=1,
            tools=[test_tool],
            tool_choice=tool_choice,
        )

        # Assertions
        mock_request.assert_called_once()
        assert result.id == "chatcmpl-789"
        assert len(result.choices) == 1
        assert result.choices[0].message.content is not None
        assert "John" in result.choices[0].message.content
        assert result.choices[0].message.tool_calls is None

    @pytest.mark.asyncio
    @patch.object(UiPathLlmChatService, "request_async")
    async def test_no_tools_mocked(self, mock_request, llm_service):
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "chatcmpl-abc",
            "object": "chat.completion",
            "created": 1677858242,
            "model": "gpt-4o-mini-2024-07-18",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Silently coding,\nPython's logic unfolds clear,\nBugs hide, then reveal.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 40,
                "completion_tokens": 20,
                "total_tokens": 60,
                "cache_read_input_tokens": None,
            },
        }
        mock_request.return_value = mock_response

        # Test messages
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write a haiku about Python programming."},
        ]

        # Call the method
        result = await llm_service.chat_completions(
            messages=messages,
            model=ChatModels.gpt_4o_mini_2024_07_18,
            max_tokens=100,
            temperature=0.7,
        )

        # Assertions
        mock_request.assert_called_once()
        assert result.id == "chatcmpl-abc"
        assert len(result.choices) == 1
        assert result.choices[0].message.content is not None
        assert len(result.choices[0].message.content.strip()) > 0
        assert result.choices[0].message.tool_calls is None

        # Verify the correct payload was sent
        args, kwargs = mock_request.call_args
        assert json.loads(kwargs["content"])["messages"] == messages
        assert json.loads(kwargs["content"])["max_tokens"] == 100
        assert json.loads(kwargs["content"])["temperature"] == 0.7
