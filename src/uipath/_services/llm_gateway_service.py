import json
from typing import Any, Dict, List, Optional

from .._config import Config
from .._execution_context import ExecutionContext
from .._utils import Endpoint
from ..models.llm_gateway import (
    ChatCompletion,
    SpecificToolChoice,
    TextEmbedding,
    ToolChoice,
    ToolDefinition,
    UsageInfo,
)
from ..tracing._traced import traced
from ._base_service import BaseService

# Common constants
API_VERSION = "2024-10-21"
NORMALIZED_API_VERSION = "2024-08-01-preview"

# Common headers
DEFAULT_LLM_HEADERS = {
    "X-UIPATH-STREAMING-ENABLED": "false",
    "X-UiPath-LlmGateway-RequestingProduct": "uipath-python-sdk",
    "X-UiPath-LlmGateway-RequestingFeature": "langgraph-agent",
}


class ChatModels(object):
    gpt_4 = "gpt-4"
    gpt_4_1106_Preview = "gpt-4-1106-Preview"
    gpt_4_32k = "gpt-4-32k"
    gpt_4_turbo_2024_04_09 = "gpt-4-turbo-2024-04-09"
    gpt_4_vision_preview = "gpt-4-vision-preview"
    gpt_4o_2024_05_13 = "gpt-4o-2024-05-13"
    gpt_4o_2024_08_06 = "gpt-4o-2024-08-06"
    gpt_4o_mini_2024_07_18 = "gpt-4o-mini-2024-07-18"
    o3_mini = "o3-mini-2025-01-31"


class EmbeddingModels(object):
    text_embedding_3_large = "text-embedding-3-large"
    text_embedding_ada_002 = "text-embedding-ada-002"


API_VERSION = "2024-10-21"
NORMALIZED_API_VERSION = "2024-08-01-preview"


class UiPathOpenAIService(BaseService):
    """Service calling llm gateway service."""

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="llm_embeddings_usage", run_type="uipath")
    async def embeddings_usage(
        self, input: str, embedding_model: str = EmbeddingModels.text_embedding_ada_002
    ):
        """Embedd the input text using llm gateway service.

        Args:
            input (str): The input text to embedd.
            embedding_model (str, optional): The embedding model to use. Defaults to text-embedding-ada-002.

        Returns:
            EmbeddingUsageInfo: The embedding usage information.
        """
        endpoint = Endpoint(
            f"/llmgateway_/openai/deployments/{embedding_model}/embeddings/usage"
        )

        response = await self.request_async(
            "POST",
            endpoint,
            content=json.dumps({"input": input}),
            params={"api-version": API_VERSION},
            headers=DEFAULT_LLM_HEADERS,
        )

        return UsageInfo.model_validate(response.json())

    @traced(name="llm_embeddings", run_type="uipath")
    async def embeddings(
        self, input: str, embedding_model: str = EmbeddingModels.text_embedding_ada_002
    ):
        """Embed the input text using llm gateway service.

        Args:
            input (str): The input text to embed.

        Returns:
            TextEmbedding: The embedding response.
        """
        endpoint = Endpoint(
            f"/llmgateway_/openai/deployments/{embedding_model}/embeddings"
        )

        response = await self.request_async(
            "POST",
            endpoint,
            content=json.dumps({"input": input}),
            params={"api-version": API_VERSION},
            headers=DEFAULT_LLM_HEADERS,
        )

        return TextEmbedding.model_validate(response.json())

    @traced(name="llm_chat_completions", run_type="uipath")
    async def chat_completions(
        self,
        messages: List[Dict[str, str]],
        model: str = ChatModels.gpt_4o_mini_2024_07_18,
        max_tokens: int = 50,
        temperature: float = 0,
    ):
        """Get chat completions using llm gateway service.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with 'role' and 'content' keys.
                The supported roles are 'system', 'user', and 'assistant'.

        Example:
                ```
                [
                    {"role": "system", "content": "You are a helpful Python programming assistant."},
                    {"role": "user", "content": "How do I read a file in Python?"},
                    {"role": "assistant", "content": "You can use the built-in open() function."},
                    {"role": "user", "content": "Can you show an example?"}
                ]
                ```
                The conversation history can be included to provide context to the model.
            model (str, optional): The model to use for chat completion. Defaults to ChatModels.gpt_4o_mini_2024_07_18.
            max_tokens (int, optional): Maximum number of tokens to generate. Defaults to 50.
            temperature (float, optional): Temperature for sampling, between 0 and 1.
                Lower values make output more deterministic. Defaults to 0.

        Returns:
            ChatCompletion: The chat completion response.
        """
        endpoint = Endpoint(f"/llmgateway_/openai/deployments/{model}/chat/completions")

        request_body = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        response = await self.request_async(
            "POST",
            endpoint,
            content=json.dumps(request_body),
            params={"api-version": API_VERSION},
            headers=DEFAULT_LLM_HEADERS,
        )

        return ChatCompletion.model_validate(response.json())

    @traced(name="llm_chat_completions_usage", run_type="uipath")
    async def chat_completions_usage(
        self,
        messages: List[Dict[str, str]],
        model: str = ChatModels.gpt_4o_mini_2024_07_18,
        max_tokens: int = 50,
        temperature: float = 0,
    ):
        """Get chat completions usage using llm gateway service.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with 'role' and 'content' keys.
                The supported roles are 'system', 'user', and 'assistant'.

        Example:
                ```
                [
                    {"role": "system", "content": "You are a helpful Python programming assistant."},
                    {"role": "user", "content": "How do I read a file in Python?"},
                    {"role": "assistant", "content": "You can use the built-in open() function."},
                    {"role": "user", "content": "Can you show an example?"}
                ]
                ```
                The conversation history can be included to provide context to the model.
            model (str, optional): The model to use for chat completion. Defaults to ChatModels.gpt_4o_mini_2024_07_18.
            max_tokens (int, optional): Maximum number of tokens to generate. Defaults to 50.
            temperature (float, optional): Temperature for sampling, between 0 and 1.
                Lower values make output more deterministic. Defaults to 0.

        Returns:
            ChatCompletion: The chat completion usage response.
        """
        endpoint = Endpoint(
            f"/llmgateway_/openai/deployments/{model}/chat/completions/usage"
        )

        request_body = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        response = await self.request_async(
            "POST",
            endpoint,
            content=json.dumps(request_body),
            params={"api-version": API_VERSION},
            headers=DEFAULT_LLM_HEADERS,
        )

        return UsageInfo.model_validate(response.json())


class UiPathLlmChatService(BaseService):
    """Service for calling UiPath's normalized LLM Gateway API."""

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="llm_chat_completions", run_type="uipath")
    async def chat_completions(
        self,
        messages: List[Dict[str, str]],
        model: str = ChatModels.gpt_4o_mini_2024_07_18,
        max_tokens: int = 250,
        temperature: float = 0,
        n: int = 1,
        frequency_penalty: float = 0,
        presence_penalty: float = 0,
        top_p: float = 1,
        tools: Optional[List[ToolDefinition]] = None,
        tool_choice: Optional[ToolChoice] = None,
    ):
        """Get chat completions using UiPath's normalized LLM Gateway API.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with 'role' and 'content' keys.
                The supported roles are 'system', 'user', and 'assistant'.
            model (str, optional): The model to use for chat completion. Defaults to ChatModels.gpt_4o_mini_2024_07_18.
            max_tokens (int, optional): Maximum number of tokens to generate. Defaults to 250.
            temperature (float, optional): Temperature for sampling, between 0 and 1.
                Lower values make output more deterministic. Defaults to 0.
            n (int, optional): Number of chat completion choices to generate. Defaults to 1.
            frequency_penalty (float, optional): Penalty for token frequency. Defaults to 0.
            presence_penalty (float, optional): Penalty for token presence. Defaults to 0.
            top_p (float, optional): Nucleus sampling parameter. Defaults to 1.
            tools (Optional[List[ToolDefinition]], optional): List of tool definitions. Defaults to None.
            tool_choice (Optional[ToolChoice], optional): Tool choice configuration.
                Can be "auto", "none", an AutoToolChoice, a RequiredToolChoice, or a SpecificToolChoice. Defaults to None.

        Returns:
            ChatCompletion: The chat completion response.
        """
        endpoint = Endpoint("/llmgateway_/api/chat/completions")

        request_body = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "n": n,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "top_p": top_p,
        }

        # Add tools if provided - convert to UiPath format
        if tools:
            request_body["tools"] = [
                self._convert_tool_to_uipath_format(tool) for tool in tools
            ]

        # Handle tool_choice
        if tool_choice:
            if isinstance(tool_choice, str):
                request_body["tool_choice"] = tool_choice
            elif isinstance(tool_choice, SpecificToolChoice):
                request_body["tool_choice"] = {"type": "tool", "name": tool_choice.name}
            else:
                request_body["tool_choice"] = tool_choice.model_dump()

        # Use default headers but update with normalized API specific headers
        headers = {
            **DEFAULT_LLM_HEADERS,
            "X-UiPath-LlmGateway-NormalizedApi-ModelName": model,
        }

        response = await self.request_async(
            "POST",
            endpoint,
            content=json.dumps(request_body),
            params={"api-version": NORMALIZED_API_VERSION},
            headers=headers,
        )

        return ChatCompletion.model_validate(response.json())

    def _convert_tool_to_uipath_format(self, tool: ToolDefinition) -> Dict[str, Any]:
        """Convert an OpenAI-style tool definition directly to UiPath API format."""
        parameters = {
            "type": tool.function.parameters.type,
            "properties": {
                name: {
                    "type": prop.type,
                    **({"description": prop.description} if prop.description else {}),
                    **({"enum": prop.enum} if prop.enum else {}),
                }
                for name, prop in tool.function.parameters.properties.items()
            },
        }

        if tool.function.parameters.required:
            parameters["required"] = tool.function.parameters.required

        return {
            "name": tool.function.name,
            "description": tool.function.description,
            "parameters": parameters,
        }
