"""UiPath LLM Gateway Services.

This module provides services for interacting with UiPath's LLM (Large Language Model) Gateway,
offering both OpenAI-compatible and normalized API interfaces for chat completions and embeddings.

The module includes:
- UiPathOpenAIService: OpenAI-compatible API for chat completions and embeddings
- UiPathLlmChatService: UiPath's normalized API with advanced features like tool calling
- ChatModels: Constants for available chat models
- EmbeddingModels: Constants for available embedding models

Classes:
    ChatModels: Container for supported chat model identifiers
    EmbeddingModels: Container for supported embedding model identifiers
    UiPathOpenAIService: Service using OpenAI-compatible API format
    UiPathLlmChatService: Service using UiPath's normalized API format
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

from .._config import Config
from .._execution_context import ExecutionContext
from .._utils import Endpoint
from ..models.llm_gateway import (
    ChatCompletion,
    SpecificToolChoice,
    TextEmbedding,
    ToolChoice,
    ToolDefinition,
)
from ..tracing import traced
from ..utils import EndpointManager
from ._base_service import BaseService

# Common constants
API_VERSION = "2024-10-21"  # Standard API version for OpenAI-compatible endpoints
NORMALIZED_API_VERSION = (
    "2024-08-01-preview"  # API version for UiPath's normalized endpoints
)

# Common headers used across all LLM Gateway requests
DEFAULT_LLM_HEADERS = {
    "X-UIPATH-STREAMING-ENABLED": "false",
    "X-UiPath-LlmGateway-RequestingProduct": "uipath-python-sdk",
    "X-UiPath-LlmGateway-RequestingFeature": "langgraph-agent",
}


class ChatModels(object):
    """Available chat models for LLM Gateway services.

    This class provides constants for the supported chat models that can be used
    with both UiPathOpenAIService and UiPathLlmChatService.
    """

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
    """Available embedding models for LLM Gateway services.

    This class provides constants for the supported embedding models that can be used
    with the embeddings functionality.
    """

    text_embedding_3_large = "text-embedding-3-large"
    text_embedding_ada_002 = "text-embedding-ada-002"


def _cleanup_schema(model_class: type[BaseModel]) -> Dict[str, Any]:
    """Clean up a Pydantic model schema for use with LLM Gateway.

    This function converts a Pydantic model's JSON schema to a format that's
    compatible with the LLM Gateway's JSON schema requirements by removing
    titles and other metadata that might cause validation issues.

    Args:
        model_class (type[BaseModel]): A Pydantic BaseModel class to convert to schema.

    Returns:
        dict: A cleaned JSON schema dictionary suitable for LLM Gateway response_format.

    Examples:
        ```python
        from pydantic import BaseModel
        from typing import List

        class Country(BaseModel):
            name: str
            capital: str
            languages: List[str]

        schema = _cleanup_schema(Country)
        # Returns a clean schema without titles and unnecessary metadata
        ```
    """
    schema = model_class.model_json_schema()

    def clean_type(type_def):
        """Clean property definitions by removing titles and cleaning nested items. Additionally, `additionalProperties` is ensured on all objects."""
        cleaned_type = {}
        for key, value in type_def.items():
            if key == "title" or key == "properties":
                continue
            else:
                cleaned_type[key] = value
        if type_def.get("type") == "object" and "additionalProperties" not in type_def:
            cleaned_type["additionalProperties"] = False

        if "properties" in type_def:
            properties = type_def.get("properties", {})
            for key, value in properties.items():
                properties[key] = clean_type(value)
            cleaned_type["properties"] = properties

        if type_def.get("type") == "object":
            cleaned_type["required"] = list(cleaned_type.get("properties", {}).keys())

        if "$defs" in type_def:
            cleaned_defs = {}
            for key, value in type_def["$defs"].items():
                cleaned_defs[key] = clean_type(value)
            cleaned_type["$defs"] = cleaned_defs
        return cleaned_type

    # Create clean schema
    clean_schema = clean_type(schema)
    return clean_schema


class UiPathOpenAIService(BaseService):
    """Service for calling UiPath's LLM Gateway using OpenAI-compatible API.

    This service provides access to Large Language Model capabilities through UiPath's
    LLM Gateway, including chat completions and text embeddings. It uses the OpenAI-compatible
    API format and is suitable for applications that need direct OpenAI API compatibility.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="llm_embeddings", run_type="uipath")
    async def embeddings(
        self,
        input: str,
        embedding_model: str = EmbeddingModels.text_embedding_ada_002,
        openai_api_version: str = API_VERSION,
    ):
        """Generate text embeddings using UiPath's LLM Gateway service.

        This method converts input text into dense vector representations that can be used
        for semantic search, similarity calculations, and other NLP tasks.

        Args:
            input (str): The input text to embed. Can be a single sentence, paragraph,
                or document that you want to convert to embeddings.
            embedding_model (str, optional): The embedding model to use.
                Defaults to EmbeddingModels.text_embedding_ada_002.
                Available models are defined in the EmbeddingModels class.
            openai_api_version (str, optional): The OpenAI API version to use.
                Defaults to API_VERSION.

        Returns:
            TextEmbedding: The embedding response containing the vector representation
                of the input text along with metadata.

        Examples:
            ```python
            # Basic embedding
            embedding = await service.embeddings("Hello, world!")

            # Using a specific model
            embedding = await service.embeddings(
                "This is a longer text to embed",
                embedding_model=EmbeddingModels.text_embedding_3_large
            )
            ```
        """
        endpoint = EndpointManager.get_embeddings_endpoint().format(
            model=embedding_model, api_version=openai_api_version
        )
        endpoint = Endpoint("/" + endpoint)

        response = await self.request_async(
            "POST",
            endpoint,
            json={"input": input},
            params={"api-version": API_VERSION},
            headers=DEFAULT_LLM_HEADERS,
        )

        return TextEmbedding.model_validate(response.json())

    @traced(name="llm_chat_completions", run_type="uipath")
    async def chat_completions(
        self,
        messages: List[Dict[str, str]],
        model: str = ChatModels.gpt_4o_mini_2024_07_18,
        max_tokens: int = 4096,
        temperature: float = 0,
        response_format: Optional[Union[Dict[str, Any], type[BaseModel]]] = None,
        api_version: str = API_VERSION,
    ):
        """Generate chat completions using UiPath's LLM Gateway service.

        This method provides conversational AI capabilities by sending a series of messages
        to a language model and receiving a generated response. It supports multi-turn
        conversations and various OpenAI-compatible models.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with 'role' and 'content' keys.
                The supported roles are 'system', 'user', and 'assistant'. System messages set
                the behavior/context, user messages are from the human, and assistant messages
                are from the AI.
            model (str, optional): The model to use for chat completion.
                Defaults to ChatModels.gpt_4o_mini_2024_07_18.
                Available models are defined in the ChatModels class.
            max_tokens (int, optional): Maximum number of tokens to generate in the response.
                Defaults to 4096. Higher values allow longer responses.
            temperature (float, optional): Temperature for sampling, between 0 and 1.
                Lower values (closer to 0) make output more deterministic and focused,
                higher values make it more creative and random. Defaults to 0.
            response_format (Optional[Union[Dict[str, Any], type[BaseModel]]], optional):
                An object specifying the format that the model must output. Can be either:
                - A dictionary with response format configuration (traditional format)
                - A Pydantic BaseModel class (automatically converted to JSON schema)
                Used to enable JSON mode or other structured outputs. Defaults to None.
            api_version (str, optional): The API version to use. Defaults to API_VERSION.

        Returns:
            ChatCompletion: The chat completion response containing the generated message,
                usage statistics, and other metadata.

        Examples:
            ```python
            # Simple conversation
            messages = [
                {"role": "system", "content": "You are a helpful Python programming assistant."},
                {"role": "user", "content": "How do I read a file in Python?"}
            ]
            response = await service.chat_completions(messages)

            # Multi-turn conversation with more tokens
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is machine learning?"},
                {"role": "assistant", "content": "Machine learning is a subset of AI..."},
                {"role": "user", "content": "Can you give me a practical example?"}
            ]
            response = await service.chat_completions(
                messages,
                max_tokens=200,
                temperature=0.3
            )

            # Using Pydantic model for structured response
            from pydantic import BaseModel
            from typing import List

            class Country(BaseModel):
                name: str
                capital: str
                languages: List[str]

            response = await service.chat_completions(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Respond with structured JSON."},
                    {"role": "user", "content": "Tell me about Canada."}
                ],
                response_format=Country,  # Pass BaseModel directly
                max_tokens=1000
            )
            ```

        Note:
            The conversation history can be included to provide context to the model.
            Each message should have both 'role' and 'content' keys.
            When using a Pydantic BaseModel as response_format, it will be automatically
            converted to the appropriate JSON schema format for the LLM Gateway.
        """
        endpoint = EndpointManager.get_passthrough_endpoint().format(
            model=model, api_version=api_version
        )
        endpoint = Endpoint("/" + endpoint)

        request_body = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Handle response_format - convert BaseModel to schema if needed
        if response_format:
            if isinstance(response_format, type) and issubclass(
                response_format, BaseModel
            ):
                # Convert Pydantic model to JSON schema format
                cleaned_schema = _cleanup_schema(response_format)
                request_body["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_format.__name__.lower(),
                        "strict": True,
                        "schema": cleaned_schema,
                    },
                }
            else:
                # Use provided dictionary format directly
                request_body["response_format"] = response_format

        response = await self.request_async(
            "POST",
            endpoint,
            json=request_body,
            params={"api-version": API_VERSION},
            headers=DEFAULT_LLM_HEADERS,
        )

        return ChatCompletion.model_validate(response.json())


class UiPathLlmChatService(BaseService):
    """Service for calling UiPath's normalized LLM Gateway API.

    This service provides access to Large Language Model capabilities through UiPath's
    normalized LLM Gateway API. Unlike the OpenAI-compatible service, this service uses
    UiPath's standardized API format and supports advanced features like tool calling,
    function calling, and more sophisticated conversation control.

    The normalized API provides a consistent interface across different underlying model
    providers and includes enhanced features for enterprise use cases.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="llm_chat_completions", run_type="uipath")
    async def chat_completions(
        self,
        messages: Union[List[Dict[str, str]], List[tuple[str, str]]],
        model: str = ChatModels.gpt_4o_mini_2024_07_18,
        max_tokens: int = 4096,
        temperature: float = 0,
        n: int = 1,
        frequency_penalty: float = 0,
        presence_penalty: float = 0,
        top_p: Optional[float] = 1,
        top_k: Optional[int] = None,
        tools: Optional[List[ToolDefinition]] = None,
        tool_choice: Optional[ToolChoice] = None,
        response_format: Optional[Union[Dict[str, Any], type[BaseModel]]] = None,
        api_version: str = NORMALIZED_API_VERSION,
    ):
        """Generate chat completions using UiPath's normalized LLM Gateway API.

        This method provides advanced conversational AI capabilities with support for
        tool calling, function calling, and sophisticated conversation control parameters.
        It uses UiPath's normalized API format for consistent behavior across different
        model providers.

        Args:
            messages (List[Dict[str, str]]): List of message dictionaries with 'role' and 'content' keys.
                The supported roles are 'system', 'user', and 'assistant'. System messages set
                the behavior/context, user messages are from the human, and assistant messages
                are from the AI.
            model (str, optional): The model to use for chat completion.
                Defaults to ChatModels.gpt_4o_mini_2024_07_18.
                Available models are defined in the ChatModels class.
            max_tokens (int, optional): Maximum number of tokens to generate in the response.
                Defaults to 4096. Higher values allow longer responses.
            temperature (float, optional): Temperature for sampling, between 0 and 1.
                Lower values (closer to 0) make output more deterministic and focused,
                higher values make it more creative and random. Defaults to 0.
            n (int, optional): Number of chat completion choices to generate for each input.
                Defaults to 1. Higher values generate multiple alternative responses.
            frequency_penalty (float, optional): Penalty for token frequency between -2.0 and 2.0.
                Positive values reduce repetition of frequent tokens. Defaults to 0.
            presence_penalty (float, optional): Penalty for token presence between -2.0 and 2.0.
                Positive values encourage discussion of new topics. Defaults to 0.
            top_p (float, optional): Nucleus sampling parameter between 0 and 1.
                Controls diversity by considering only the top p probability mass. Defaults to 1.
            top_k (int, optional): Nucleus sampling parameter.
                Controls diversity by considering only the top k most probable tokens. Defaults to None.
            tools (Optional[List[ToolDefinition]], optional): List of tool definitions that the
                model can call. Tools enable the model to perform actions or retrieve information
                beyond text generation. Defaults to None.
            tool_choice (Optional[ToolChoice], optional): Controls which tools the model can call.
                Can be "auto" (model decides), "none" (no tools), or a specific tool choice.
                Defaults to None.
            response_format (Optional[Union[Dict[str, Any], type[BaseModel]]], optional):
                An object specifying the format that the model must output. Can be either:
                - A dictionary with response format configuration (traditional format)
                - A Pydantic BaseModel class (automatically converted to JSON schema)
                Used to enable JSON mode or other structured outputs. Defaults to None.
            api_version (str, optional): The normalized API version to use.
                Defaults to NORMALIZED_API_VERSION.

        Returns:
            ChatCompletion: The chat completion response containing the generated message(s),
                tool calls (if any), usage statistics, and other metadata.

        Examples:
            ```python
            # Basic conversation
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the weather like today?"}
            ]
            response = await service.chat_completions(messages)

            # Conversation with tool calling
            tools = [
                ToolDefinition(
                    function=FunctionDefinition(
                        name="get_weather",
                        description="Get current weather for a location",
                        parameters=ParametersDefinition(
                            type="object",
                            properties={
                                "location": PropertyDefinition(
                                    type="string",
                                    description="City name"
                                )
                            },
                            required=["location"]
                        )
                    )
                )
            ]
            response = await service.chat_completions(
                messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=500
            )

            # Advanced parameters for creative writing
            response = await service.chat_completions(
                messages,
                temperature=0.8,
                top_p=0.9,
                frequency_penalty=0.3,
                presence_penalty=0.2,
                n=3  # Generate 3 alternative responses
            )

            # Using Pydantic model for structured response
            from pydantic import BaseModel
            from typing import List

            class Country(BaseModel):
                name: str
                capital: str
                languages: List[str]

            response = await service.chat_completions(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Respond with structured JSON."},
                    {"role": "user", "content": "Tell me about Canada."}
                ],
                response_format=Country,  # Pass BaseModel directly
                max_tokens=1000
            )
            )
            ```

        Note:
            This service uses UiPath's normalized API format which provides consistent
            behavior across different underlying model providers and enhanced enterprise features.
        """
        converted_messages = []

        for message in messages:
            if isinstance(message, tuple) and len(message) == 2:
                role, content = message
                converted_messages.append({"role": role, "content": content})
            elif isinstance(message, dict):
                converted_messages.append(message)
            else:
                raise ValueError(
                    f"Invalid message format: {message}. Expected tuple (role, content) or dict with 'role' and 'content' keys."
                )

        endpoint = EndpointManager.get_normalized_endpoint().format(
            model=model, api_version=api_version
        )
        endpoint = Endpoint("/" + endpoint)

        request_body = {
            "messages": converted_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "n": n,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "top_p": top_p,
        }
        if top_k is not None:
            request_body["top_k"] = top_k

        # Handle response_format - convert BaseModel to schema if needed
        if response_format:
            if isinstance(response_format, type) and issubclass(
                response_format, BaseModel
            ):
                # Convert Pydantic model to JSON schema format
                cleaned_schema = _cleanup_schema(response_format)
                request_body["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": response_format.__name__.lower(),
                        "strict": True,
                        "schema": cleaned_schema,
                    },
                }
            else:
                # Use provided dictionary format directly
                request_body["response_format"] = response_format

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
            json=request_body,
            params={"api-version": NORMALIZED_API_VERSION},
            headers=headers,
        )

        return ChatCompletion.model_validate(response.json())

    def _convert_tool_to_uipath_format(self, tool: ToolDefinition) -> Dict[str, Any]:
        """Convert an OpenAI-style tool definition to UiPath API format.

        This internal method transforms tool definitions from the standard OpenAI format
        to the format expected by UiPath's normalized LLM Gateway API.

        Args:
            tool (ToolDefinition): The tool definition in OpenAI format containing
                function name, description, and parameter schema.

        Returns:
            Dict[str, Any]: The tool definition converted to UiPath API format
                with the appropriate structure and field mappings.
        """
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
