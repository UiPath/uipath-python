import os
from unittest.mock import MagicMock, patch

import pytest

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.chat import (
    AutoToolChoice,
    ChatModels,
    SpecificToolChoice,
    ToolDefinition,
    ToolFunctionDefinition,
    ToolParametersDefinition,
    ToolPropertyDefinition,
    UiPathLlmChatService,
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
        # skip tests on CI, only run locally
        pytest.skip("Failed to get access token. Check your credentials.")

        # In a real-world scenario, these would be environment variables
        base_url = get_env_var("UIPATH_URL")
        api_key = get_env_var("UIPATH_ACCESS_TOKEN")

        config = UiPathApiConfig(base_url=base_url, secret=api_key)
        execution_context = UiPathExecutionContext()
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
            model=ChatModels.gpt_4_1_mini_2025_04_14,
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
            model=ChatModels.gpt_4_1_mini_2025_04_14,
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
            model=ChatModels.gpt_4_1_mini_2025_04_14,
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
            model=ChatModels.gpt_4_1_mini_2025_04_14,
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
        return UiPathApiConfig(base_url="https://example.com", secret="test_secret")

    @pytest.fixture
    def execution_context(self):
        return UiPathExecutionContext()

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
            model=ChatModels.gpt_4_1_mini_2025_04_14,
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
        assert "/orchestrator_/llm/api/chat/completions" in args[1]
        assert kwargs["json"]["messages"] == messages
        assert kwargs["json"]["max_tokens"] == 50
        assert kwargs["json"]["temperature"] == 0

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
            model=ChatModels.gpt_4_1_mini_2025_04_14,
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
            model=ChatModels.gpt_4_1_mini_2025_04_14,
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
            model=ChatModels.gpt_4_1_mini_2025_04_14,
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
        assert kwargs["json"]["messages"] == messages
        assert kwargs["json"]["max_tokens"] == 100
        assert kwargs["json"]["temperature"] == 0.7

    @pytest.mark.asyncio
    @patch.object(UiPathLlmChatService, "request_async")
    async def test_anthropic_model_excludes_openai_params(
        self, mock_request, llm_service
    ):
        """Test that Anthropic models don't receive OpenAI-specific parameters."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "msg_123",
            "object": "chat.completion",
            "created": 1677858242,
            "model": "anthropic.claude-haiku-4-5-20251001-v1:0",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello! How can I help you today?",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30,
                "cache_read_input_tokens": None,
            },
        }
        mock_request.return_value = mock_response

        # Test messages
        messages = [
            {"role": "user", "content": "Hello"},
        ]

        # Call the method with an Anthropic model
        result = await llm_service.chat_completions(
            messages=messages,
            model="anthropic.claude-haiku-4-5-20251001-v1:0",
            max_tokens=100,
            temperature=0,
            n=2,  # OpenAI-specific
            frequency_penalty=0.5,  # OpenAI-specific
            presence_penalty=0.3,  # OpenAI-specific
        )

        # Assertions
        mock_request.assert_called_once()
        assert result.id == "msg_123"
        assert len(result.choices) == 1

        # Verify the request payload EXCLUDES OpenAI-specific params
        args, kwargs = mock_request.call_args
        request_body = kwargs["json"]
        assert request_body["messages"] == messages
        assert request_body["max_tokens"] == 100
        assert request_body["temperature"] == 0

        # These OpenAI-specific parameters should NOT be in the request
        assert "top_p" not in request_body  # Excluded for Anthropic models
        assert "n" not in request_body
        assert "frequency_penalty" not in request_body
        assert "presence_penalty" not in request_body

    @pytest.mark.asyncio
    @patch.object(UiPathLlmChatService, "request_async")
    async def test_anthropic_model_converts_required_tool_choice(
        self, mock_request, llm_service
    ):
        """Test that Anthropic models convert RequiredToolChoice to 'any'."""
        from uipath.platform.chat.llm_gateway import (
            RequiredToolChoice,
            ToolDefinition,
            ToolFunctionDefinition,
            ToolParametersDefinition,
            ToolPropertyDefinition,
        )

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "msg_123",
            "object": "chat.completion",
            "created": 1677858242,
            "model": "anthropic.claude-haiku-4-5-20251001-v1:0",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "name": "test_tool",
                                "arguments": {"score": 95},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30,
                "cache_read_input_tokens": None,
            },
        }
        mock_request.return_value = mock_response

        # Test messages
        messages = [
            {"role": "user", "content": "Evaluate this response"},
        ]

        # Define a test tool
        test_tool = ToolDefinition(
            type="function",
            function=ToolFunctionDefinition(
                name="submit_score",
                description="Submit evaluation score",
                parameters=ToolParametersDefinition(
                    type="object",
                    properties={
                        "score": ToolPropertyDefinition(
                            type="number", description="Score from 0-100"
                        ),
                    },
                    required=["score"],
                ),
            ),
        )

        # Call the method with RequiredToolChoice (OpenAI format)
        result = await llm_service.chat_completions(
            messages=messages,
            model="anthropic.claude-haiku-4-5-20251001-v1:0",
            max_tokens=100,
            temperature=0,
            tools=[test_tool],
            tool_choice=RequiredToolChoice(),  # This should be converted to "any"
        )

        # Assertions
        mock_request.assert_called_once()
        assert result.id == "msg_123"

        # Verify the request payload converted tool_choice
        args, kwargs = mock_request.call_args
        request_body = kwargs["json"]

        # Anthropic should receive "any" instead of {"type": "required"}
        assert request_body["tool_choice"] == "any"
        assert request_body["tool_choice"] != {"type": "required"}

    @pytest.mark.asyncio
    @patch.object(UiPathLlmChatService, "request_async")
    async def test_openai_model_includes_all_params(self, mock_request, llm_service):
        """Test that OpenAI models receive all parameters including OpenAI-specific ones."""
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
                        "content": "Hello! How can I help you today?",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 10,
                "total_tokens": 30,
                "cache_read_input_tokens": None,
            },
        }
        mock_request.return_value = mock_response

        # Test messages
        messages = [
            {"role": "user", "content": "Hello"},
        ]

        # Call the method with an OpenAI model
        result = await llm_service.chat_completions(
            messages=messages,
            model=ChatModels.gpt_4o_mini_2024_07_18,
            max_tokens=100,
            temperature=0,
            n=2,
            frequency_penalty=0.5,
            presence_penalty=0.3,
        )

        # Assertions
        mock_request.assert_called_once()
        assert result.id == "chatcmpl-123"

        # Verify the request payload INCLUDES all parameters
        args, kwargs = mock_request.call_args
        request_body = kwargs["json"]
        assert request_body["messages"] == messages
        assert request_body["max_tokens"] == 100
        assert request_body["temperature"] == 0
        assert request_body["top_p"] == 1

        # These OpenAI-specific parameters SHOULD be in the request
        assert request_body["n"] == 2
        assert request_body["frequency_penalty"] == 0.5
        assert request_body["presence_penalty"] == 0.3
